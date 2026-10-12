"""Read-only live smoke probe; never prints auth headers, tokens, or response bodies."""
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent-service"))

from app.solver.runner import DEFAULT_BACKEND_URL, _get_default_token  # noqa: E402
from app.llm_client import load_models_config, _load_env_var  # noqa: E402


def main() -> int:
    base = os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
    timeout = httpx.Timeout(120.0, connect=20.0)
    token = _get_default_token()
    failures = 0

    def request(method: str, path: str, expected: tuple[int, ...], auth: bool = False):
        nonlocal failures
        try:
            headers = {"X-Dev-Token": token} if auth else {}
            response = httpx.request(method, f"{base}{path}", headers=headers, timeout=timeout)
            ok = response.status_code in expected
            print(f"{method} {path}: HTTP {response.status_code} {'PASS' if ok else 'FAIL'}")
            if not ok:
                failures += 1
            return response
        except httpx.HTTPError as exc:
            print(f"{method} {path}: NETWORK {type(exc).__name__} FAIL")
            failures += 1
            return None

    request("GET", "/health", (200,))
    request("GET", "/health/database", (200,), auth=True)
    spec_response = request("GET", "/openapi.json", (200,))
    if spec_response and spec_response.status_code == 200:
        spec = spec_response.json()
        paths = spec.get("paths", {})
        print(f"OpenAPI paths: {len(paths)}")
        print("Calculation endpoints present:", all(path in paths for path in (
            "/tasks/{task_id}/calculation-input", "/tasks/{task_id}/calculate", "/tasks/{task_id}/result"
        )))

    # Distinguish valid auth from invalid ID; 404 proves auth accepted, 401 does not.
    auth_probe = request("GET", "/tasks/VO-AUTH-PROBE-NOTFOUND", (404,), auth=True)
    if auth_probe and auth_probe.status_code == 401:
        failures += 1
    request("GET", "/tasks/VO-AUTH-PROBE-NOTFOUND", (401,), auth=False)

    router = _load_env_var("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    key = _load_env_var("OPENROUTER_API_KEY", "")
    model_cfg = load_models_config()
    target_model = model_cfg["ie_agent"]["model"]
    try:
        response = httpx.get(f"{router}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
        ids = [entry.get("id") for entry in response.json().get("data", [])] if response.status_code == 200 else []
        print(f"OpenRouter /v1/models: HTTP {response.status_code} {'PASS' if response.status_code == 200 else 'FAIL'}; model_present={target_model in ids}")
        if response.status_code != 200 or target_model not in ids:
            failures += 1
    except (httpx.HTTPError, ValueError):
        print("OpenRouter /v1/models: NETWORK/JSON FAIL")
        failures += 1

    print(f"RESULT: {'PASS' if failures == 0 else 'FAIL'} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
