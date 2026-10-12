"""Shared mode-aware fixtures. Test secrets are loaded but never printed."""
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return values
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_DOTENV = _read_dotenv()


def secret(name: str, default: str = "") -> str:
    return os.environ.get(name) or _DOTENV.get(name, default)


def pytest_configure(config):
    config.addinivalue_line("markers", "live: makes calls to real backend, OpenRouter, or agent service")
    config.addinivalue_line("markers", "mock: isolated deterministic test using mocks")


@pytest.fixture(scope="session")
def test_mode() -> str:
    return os.environ.get("TEST_MODE", "mock").lower()


@pytest.fixture(scope="session")
def backend_config() -> dict[str, str]:
    return {
        "base_url": secret("BACKEND_URL", "https://stock-copilot-backend.onrender.com").rstrip("/"),
        "token": secret("DEV_TOKEN"),
    }


@pytest.fixture(scope="session")
def openrouter_config() -> dict[str, str]:
    return {
        "base_url": secret("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
        "api_key": secret("OPENROUTER_API_KEY"),
    }


@pytest.fixture(scope="session")
def live_http_client():
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
        yield client


@pytest.fixture(scope="session")
def ensure_agent_service():
    """Start a local service only when absent; never pass credentials on CLI or log output."""
    base = os.environ.get("AGENT_SERVICE_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        if httpx.get(f"{base}/health", timeout=1).status_code == 200:
            yield
            return
    except httpx.HTTPError:
        pass

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=PROJECT_ROOT / "agent-service",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail("agent-service exited before its health endpoint became ready")
            try:
                if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            pytest.fail("agent-service did not become healthy within 45 seconds")
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def pytest_collection_modifyitems(config, items):
    mode = os.environ.get("TEST_MODE", "mock").lower()
    skip_live = pytest.mark.skip(reason="Set TEST_MODE=live to run live integrations")
    for item in items:
        if item.get_closest_marker("live") and mode != "live":
            item.add_marker(skip_live)
        elif not item.get_closest_marker("live") and not item.get_closest_marker("mock"):
            item.add_marker(pytest.mark.mock)
