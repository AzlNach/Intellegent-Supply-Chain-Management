import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
import yaml
from openai import (
    APIConnectionError,
    APIError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

logger = logging.getLogger("llm_client")

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "models.yaml")


class LLMClientError(Exception):
    """Base exception for LLM Client."""
    pass


class RoleDisabledError(LLMClientError):
    """Raised when attempting to use a disabled or inactive role."""
    pass


class ConfigurationError(LLMClientError):
    """Raised when models.yaml or configuration is invalid."""
    pass


def _load_env_var(key: str, default: str = "") -> str:
    """Load variable from os.environ or .env file."""
    val = os.environ.get(key)
    if val:
        return val.strip().strip('"').strip("'")

    env_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f"{key}="):
                            raw = line.split("=", 1)[1].strip()
                            return raw.strip('"').strip("'")
            except Exception:
                pass
    return default


def load_models_config(config_path: str = CONFIG_PATH) -> Dict[str, Any]:
    """Load roles configuration from models.yaml."""
    if not os.path.exists(config_path):
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "roles" not in data:
        raise ConfigurationError("Invalid models.yaml: missing 'roles' section.")

    return data["roles"]


class LLMClient:
    """
    OpenRouter OpenAI-compatible client wrapper with resilience, role mapping,
    fallback tracking, and function calling probe.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        config_path: str = CONFIG_PATH,
        check_tools_on_startup: bool = True,
        max_retries: int = 3,
        initial_backoff: float = 0.5,
    ):
        self.base_url = base_url or _load_env_var("OPENROUTER_BASE_URL", DEFAULT_BASE_URL)
        self.api_key = api_key or _load_env_var("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise ConfigurationError("OPENROUTER_API_KEY is not configured.")
        self.config_path = config_path
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            max_retries=0,
        )

        self.roles_config = load_models_config(self.config_path)
        self.supports_tools: Dict[str, bool] = {}

        if check_tools_on_startup:
            self._probe_tool_capabilities()

    def _probe_tool_capabilities(self) -> None:
        """
        Probe active roles to check if function calling is supported.
        If unsupported, log warning and fallback to structured JSON mode.
        """
        for role, cfg in self.roles_config.items():
            if not cfg.get("enabled", False):
                continue

            model = cfg.get("model")
            try:
                # Small probe call with dummy function
                probe_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "probe_ping",
                            "description": "Probe check",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ]
                self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "ping"}],
                    tools=probe_tools,
                    max_tokens=64,
                    timeout=10.0,
                )
                self.supports_tools[role] = True
                logger.info("Model '%s' for role '%s' supports function calling.", model, role)
            except Exception as e:
                self.supports_tools[role] = False
                logger.warning(
                    "Model '%s' untuk role '%s' tidak mendukung function calling: %s. "
                    "Menggunakan mode JSON terstruktur sebagai cadangan.",
                    model,
                    role,
                    str(e),
                )

    def _convert_tools_to_json_prompt(
        self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fallback adapter: inject tool schema instructions for structured JSON mode."""
        formatted_messages = list(messages)
        tools_desc = []
        for t in tools:
            fn = t.get("function", {})
            name = fn.get("name", "unknown")
            desc = fn.get("description", "")
            params = fn.get("parameters", {})
            tools_desc.append(f"- Tool: `{name}`\n  Description: {desc}\n  Parameters: {json.dumps(params)}")

        instruction = (
            "\n\n[INSTRUCTIONS FOR FUNCTION CALLING IN STRUCTURED JSON MODE]\n"
            "If you decide to invoke a tool, respond with valid JSON in this exact structure:\n"
            '{"action": "call_tool", "name": "<tool_name>", "parameters": {<args>}}\n'
            "Available tools:\n" + "\n".join(tools_desc) + "\n"
        )

        # Append to existing system message or add new system message
        has_system = False
        for i, m in enumerate(formatted_messages):
            if m.get("role") == "system":
                formatted_messages[i] = {
                    "role": "system",
                    "content": m.get("content", "") + instruction,
                }
                has_system = True
                break

        if not has_system:
            formatted_messages.insert(0, {"role": "system", "content": instruction})

        return formatted_messages

    def chat(
        self,
        role: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute chat completion for a given role defined in models.yaml.
        Handles timeout, retries (429 & 5xx with backoff), and fallback tracking.
        Never logs prompt contents in full.
        """
        if role not in self.roles_config:
            raise LLMClientError(f"Role '{role}' not found in {self.config_path}.")

        role_cfg = self.roles_config[role]
        if not role_cfg.get("enabled", False):
            raise RoleDisabledError(f"Role '{role}' is disabled in configuration.")

        configured_model = role_cfg["model"]
        temperature = kwargs.get("temperature", role_cfg.get("temperature", 0.7))
        max_tokens = kwargs.get("max_tokens", role_cfg.get("max_tokens", 2048))
        timeout = kwargs.get("timeout", role_cfg.get("timeout", 30.0))

        # Check function calling capability
        role_supports_tools = self.supports_tools.get(role, True)
        call_tools = tools
        call_messages = messages

        if tools and not role_supports_tools:
            logger.info("Converting tools to structured JSON prompt for role '%s'.", role)
            call_messages = self._convert_tools_to_json_prompt(messages, tools)
            call_tools = None

        # Sanitize log: log message count and lengths, NEVER prompt content in full
        msg_counts = len(call_messages)
        content_lengths = sum(len(str(m.get("content", ""))) for m in call_messages)
        logger.info(
            "Calling LLM for role='%s', model='%s', messages_count=%d, total_chars=%d",
            role,
            configured_model,
            msg_counts,
            content_lengths,
        )

        model_candidates = [configured_model, *role_cfg.get("fallback_models", [])]
        last_exception = None

        for model_index, request_model in enumerate(model_candidates):
            backoff = self.initial_backoff
            for attempt in range(self.max_retries + 1):
                try:
                    create_params = {
                        "model": request_model,
                        "messages": call_messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "timeout": timeout,
                    }
                    if call_tools:
                        create_params["tools"] = call_tools

                    started_at = time.time()
                    response = self.client.chat.completions.create(**create_params)
                    latency_ms = round((time.time() - started_at) * 1000, 2)

                    actual_model = getattr(response, "model", request_model)
                    fallback_used = model_index > 0 or actual_model != configured_model
                    if fallback_used:
                        logger.warning(
                            "fallback_used: Primary model '%s' answered by '%s' for role '%s'.",
                            configured_model,
                            actual_model,
                            role,
                        )

                    choice = response.choices[0] if response.choices else None
                    message_obj = choice.message if choice else None
                    content = getattr(message_obj, "content", "") if message_obj else ""
                    tool_calls = getattr(message_obj, "tool_calls", None) if message_obj else None
                    usage_data = {}
                    if getattr(response, "usage", None):
                        usage_data = {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens,
                        }

                    logger.info(
                        "LLM call completed role='%s', model='%s', latency_ms=%.2f, "
                        "prompt_tokens=%d, completion_tokens=%d, total_tokens=%d, fallback_used=%s",
                        role, actual_model, latency_ms,
                        usage_data.get("prompt_tokens", 0),
                        usage_data.get("completion_tokens", 0),
                        usage_data.get("total_tokens", 0),
                        fallback_used,
                    )
                    return {
                        "role": role,
                        "content": content,
                        "tool_calls": tool_calls,
                        "model_configured": configured_model,
                        "model_used": actual_model,
                        "fallback_used": fallback_used,
                        "usage": usage_data,
                        "raw_response": response,
                    }

                except (RateLimitError, InternalServerError, APIConnectionError) as e:
                    last_exception = e
                except APIError as e:
                    status_code = getattr(e, "status_code", 0) or 0
                    if status_code not in (400, 404, 422) and status_code < 500:
                        raise LLMClientError(f"API error for role '{role}' (HTTP {status_code}).") from e
                    last_exception = e

                if attempt < self.max_retries:
                    logger.warning(
                        "LLM request failed role='%s' model='%s' attempt=%d/%d; retry in %.2fs",
                        role, request_model, attempt + 1, self.max_retries + 1, backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2
            if model_index < len(model_candidates) - 1:
                logger.warning("Primary/fallback model exhausted for role='%s'; trying configured fallback.", role)

        raise LLMClientError(
            f"Exceeded max retries ({self.max_retries}) for role '{role}': {last_exception}"
        ) from last_exception


# Default singleton instance
_default_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create singleton LLMClient instance."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def chat(
    role: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Convenience functional wrapper for LLMClient.chat()."""
    client = get_llm_client()
    return client.chat(role=role, messages=messages, tools=tools, **kwargs)


def check_llm_health(client: Optional[LLMClient] = None) -> Dict[str, Any]:
    """
    Check connectivity to OpenRouter.
    Reports connection status, available models, and latency for /health/llm.
    """
    start_time = time.time()
    try:
        c = client or get_llm_client()
        models_resp = c.client.models.list()
        latency_ms = round((time.time() - start_time) * 1000, 2)
        model_ids = [m.id for m in models_resp.data] if hasattr(models_resp, "data") else []

        return {
            "status": "ok",
            "connected": True,
            "latency_ms": latency_ms,
            "available_models_count": len(model_ids),
            "available_models": model_ids,
        }
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "status": "error",
            "connected": False,
            "latency_ms": latency_ms,
            "error": str(e),
            "available_models": [],
        }
