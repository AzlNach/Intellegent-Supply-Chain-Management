import logging
from unittest.mock import MagicMock, patch
import pytest
from openai import RateLimitError, InternalServerError, APIError

from app.llm_client import (
    DEFAULT_BASE_URL,
    ConfigurationError,
    LLMClient,
    chat,
    check_llm_health,
    RoleDisabledError,
    LLMClientError,
)


@pytest.fixture
def mock_openai(monkeypatch):
    import app.llm_client as llm_module

    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-openrouter-key")
    monkeypatch.setattr(llm_module, "_default_client", None)
    with patch("app.llm_client.OpenAI") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.constructor = mock_cls
        mock_cls.return_value = mock_instance
        yield mock_instance


def test_chat_success(mock_openai):
    client = LLMClient(check_tools_on_startup=False)
    configured_model = client.roles_config["ie_agent"]["model"]

    # Mock successful completion with the configured model
    mock_resp = MagicMock()
    mock_resp.model = configured_model
    mock_resp.choices = [
        MagicMock(message=MagicMock(content="Halo, stok aman.", role="assistant", tool_calls=None))
    ]
    mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_openai.chat.completions.create.return_value = mock_resp

    result = client.chat(
        role="ie_agent",
        messages=[{"role": "user", "content": "Cek stok Mie A"}],
    )

    assert result["content"] == "Halo, stok aman."
    assert result["model_used"] == configured_model
    assert result["fallback_used"] is False
    assert mock_openai.chat.completions.create.call_count == 1

    # Check params passed
    call_kwargs = mock_openai.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == configured_model
    assert call_kwargs["temperature"] == 0.2
    assert call_kwargs["max_tokens"] == 2048


def test_client_defaults_to_direct_openrouter_and_reads_key_from_environment(mock_openai, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-never-log")
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    client = LLMClient(check_tools_on_startup=False)
    assert client.base_url == DEFAULT_BASE_URL == "https://openrouter.ai/api/v1"
    assert client.api_key == "test-key-never-log"
    mock_openai.constructor.assert_called_once_with(base_url=DEFAULT_BASE_URL, api_key="test-key-never-log", max_retries=0)


def test_client_fails_clearly_when_openrouter_key_is_missing(monkeypatch):
    import app.llm_client as llm_module

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(llm_module, "_load_env_var", lambda key, default="": "" if key == "OPENROUTER_API_KEY" else default)
    with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY is not configured"):
        LLMClient(check_tools_on_startup=False)


def test_chat_disabled_role():
    client = LLMClient(api_key="mock-key", check_tools_on_startup=False)
    # Role manager is disabled in models.yaml
    with pytest.raises(RoleDisabledError) as excinfo:
        client.chat(role="manager", messages=[{"role": "user", "content": "test"}])
    assert "manager" in str(excinfo.value)

    # Unknown role
    with pytest.raises(LLMClientError):
        client.chat(role="unknown_role", messages=[{"role": "user", "content": "test"}])


def test_chat_retry_on_429(mock_openai):
    # First attempt: 429 RateLimitError
    err_429 = RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429, headers={}),
        body=None,
    )

    mock_resp = MagicMock()
    mock_resp.model = "gh/gpt-4o-mini"
    mock_resp.choices = [
        MagicMock(message=MagicMock(content="Sukses setelah retry.", role="assistant", tool_calls=None))
    ]
    mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    mock_openai.chat.completions.create.side_effect = [err_429, mock_resp]

    client = LLMClient(check_tools_on_startup=False, max_retries=2, initial_backoff=0.01)
    result = client.chat(
        role="ie_agent",
        messages=[{"role": "user", "content": "Hitung gap"}],
    )

    assert result["content"] == "Sukses setelah retry."
    assert mock_openai.chat.completions.create.call_count == 2


def test_chat_retry_on_5xx(mock_openai):
    # First attempt: 500 InternalServerError
    err_500 = InternalServerError(
        message="Internal server error",
        response=MagicMock(status_code=500, headers={}),
        body=None,
    )

    mock_resp = MagicMock()
    mock_resp.model = "gh/gpt-4o-mini"
    mock_resp.choices = [
        MagicMock(message=MagicMock(content="Sukses setelah 500.", role="assistant", tool_calls=None))
    ]
    mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    mock_openai.chat.completions.create.side_effect = [err_500, mock_resp]

    client = LLMClient(check_tools_on_startup=False, max_retries=2, initial_backoff=0.01)
    result = client.chat(
        role="ie_agent",
        messages=[{"role": "user", "content": "Hitung gap"}],
    )

    assert result["content"] == "Sukses setelah 500."
    assert mock_openai.chat.completions.create.call_count == 2


def test_fallback_used_flag_when_model_differs(mock_openai, caplog):
    # OpenRouter may route the configured model to a different provider model ID.
    mock_resp = MagicMock()
    mock_resp.model = "gh/gpt-4o"
    mock_resp.choices = [
        MagicMock(message=MagicMock(content="Dijawab oleh fallback model.", role="assistant", tool_calls=None))
    ]
    mock_resp.usage = MagicMock(prompt_tokens=12, completion_tokens=8, total_tokens=20)
    mock_openai.chat.completions.create.return_value = mock_resp

    client = LLMClient(api_key="mock-key", check_tools_on_startup=False)
    with caplog.at_level(logging.WARNING):
        result = client.chat(
            role="ie_agent",
            messages=[{"role": "user", "content": "Halo"}],
        )

    assert result["fallback_used"] is True
    assert result["model_used"] == "gh/gpt-4o"
    assert "fallback_used" in caplog.text


def test_startup_tool_check_fallback_to_json_mode(mock_openai, caplog):
    # Simulate probe call failing tool calling
    mock_openai.chat.completions.create.side_effect = APIError(
        message="Function calling not supported by provider",
        request=MagicMock(),
        body=None,
    )

    with caplog.at_level(logging.WARNING):
        client = LLMClient(api_key="mock-key", check_tools_on_startup=True)

    # Function calling probe failed -> warning logged and fallback mode active
    assert client.supports_tools["ie_agent"] is False
    assert "mode JSON terstruktur sebagai cadangan" in caplog.text or "JSON" in caplog.text

    # Reset mock for chat call
    mock_resp = MagicMock()
    mock_resp.model = "gh/gpt-4o-mini"
    mock_resp.choices = [
        MagicMock(message=MagicMock(content='{"action": "call_solver"}', role="assistant", tool_calls=None))
    ]
    mock_resp.usage = MagicMock(prompt_tokens=20, completion_tokens=10, total_tokens=30)
    mock_openai.chat.completions.create.side_effect = None
    mock_openai.chat.completions.create.return_value = mock_resp

    test_tools = [
        {
            "type": "function",
            "function": {
                "name": "run_solver",
                "description": "Invoke solver engine",
                "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}},
            },
        }
    ]

    result = client.chat(
        role="ie_agent",
        messages=[{"role": "user", "content": "Tolong selesaikan task 123"}],
        tools=test_tools,
    )

    # Tools should NOT be passed in API call, but converted into structured JSON instructions in prompt
    call_kwargs = mock_openai.chat.completions.create.call_args[1]
    assert "tools" not in call_kwargs or call_kwargs["tools"] is None
    # System message or prompt should contain JSON instructions for run_solver
    sent_messages = call_kwargs["messages"]
    prompt_text = " ".join([m["content"] for m in sent_messages if isinstance(m.get("content"), str)])
    assert "run_solver" in prompt_text
    assert result["content"] == '{"action": "call_solver"}'


def test_prompt_content_not_logged_in_full(mock_openai, caplog):
    mock_resp = MagicMock()
    mock_resp.model = "gh/gpt-4o-mini"
    mock_resp.choices = [MagicMock(message=MagicMock(content="Jawaban", role="assistant", tool_calls=None))]
    mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_openai.chat.completions.create.return_value = mock_resp

    secret_prompt = "RAHASIA_SUPER_SENSITIF_12345"
    client = LLMClient(api_key="mock-key", check_tools_on_startup=False)

    with caplog.at_level(logging.DEBUG):
        client.chat(
            role="ie_agent",
            messages=[{"role": "user", "content": secret_prompt}],
        )

    # Ensure secret prompt text is NOT in any log record
    for record in caplog.records:
        assert secret_prompt not in record.message


def test_check_llm_health(mock_openai):
    mock_models_resp = MagicMock()
    mock_model_1 = MagicMock(id="gh/gpt-4o-mini")
    mock_model_2 = MagicMock(id="gh/gpt-4o")
    mock_models_resp.data = [mock_model_1, mock_model_2]
    mock_openai.models.list.return_value = mock_models_resp

    health = check_llm_health()
    assert health["status"] == "ok"
    assert health["connected"] is True
    assert "gh/gpt-4o-mini" in health["available_models"]


def test_endpoint_health_llm(mock_openai):
    from fastapi.testclient import TestClient
    from app.main import app

    mock_models_resp = MagicMock()
    mock_model_1 = MagicMock(id="gh/gpt-4o-mini")
    mock_models_resp.data = [mock_model_1]
    mock_openai.models.list.return_value = mock_models_resp

    test_client = TestClient(app)
    response = test_client.get("/health/llm")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["connected"] is True
    assert "gh/gpt-4o-mini" in data["available_models"]
