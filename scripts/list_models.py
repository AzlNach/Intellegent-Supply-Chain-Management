#!/usr/bin/env python3
"""
Helper script to fetch and list available models from OpenRouter (GET /v1/models).
"""
import os
import sys
import httpx

# Add agent-service to sys.path if needed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent-service"))

from app.llm_client import _load_env_var, DEFAULT_BASE_URL


def main():
    base_url = _load_env_var("OPENROUTER_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    api_key = _load_env_var("OPENROUTER_API_KEY", "")

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    models_url = f"{base_url}/models"
    print(f"Connecting to OpenRouter at: {models_url}")

    if not api_key:
        print("[ERROR] OPENROUTER_API_KEY is not configured.")
        sys.exit(1)

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(models_url, headers=headers)
            if resp.status_code != 200:
                print(f"[ERROR] Failed to fetch models: HTTP {resp.status_code}")
                sys.exit(1)

            data = resp.json()
            models = data.get("data", [])
            print(f"\nFound {len(models)} models available in OpenRouter:\n")
            print(f"{'#':<4} {'MODEL ID':<35} {'OWNER':<10} {'TOOLS':<8} {'CONTEXT'}")
            print("-" * 70)

            for idx, m in enumerate(models, 1):
                model_id = m.get("id", "unknown")
                owner = m.get("owned_by", "-")
                caps = m.get("capabilities", {})
                has_tools = "YES" if caps.get("tools", False) else "NO"
                ctx = m.get("context_length", caps.get("contextWindow", "-"))
                print(f"{idx:<4} {model_id:<35} {owner:<10} {has_tools:<8} {ctx}")

    except Exception as exc:
        print(f"[ERROR] Connection failed: {type(exc).__name__}")
        sys.exit(1)


if __name__ == "__main__":
    main()
