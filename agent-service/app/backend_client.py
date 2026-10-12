import logging
import os
import time
from typing import Any, Dict, Optional
import httpx

from app.config import config

logger = logging.getLogger("backend_client")


def _get_dev_token() -> str:
    """Retrieve development token from environment or .env file."""
    token = os.getenv("DEV_TOKEN") or os.getenv("X_DEV_TOKEN")
    if token:
        return token.strip().strip('"').strip("'")

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
                        if line.startswith("DEV_TOKEN="):
                            raw = line.split("=", 1)[1].strip()
                            return raw.strip('"').strip("'")
            except Exception:
                pass
    return ""


class BackendAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class BackendClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        client: Optional[httpx.Client] = None,
    ):
        self.base_url = (base_url or config.backend_url).rstrip("/")
        self.token = token or _get_dev_token()
        self._external_client = client

    def _get_client(self) -> httpx.Client:
        if self._external_client:
            return self._external_client
        return httpx.Client(base_url=self.base_url, timeout=30.0)

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}" if not path.startswith("http") else path
        headers = {
            "X-Dev-Token": self.token,
            "Content-Type": "application/json",
        }

        # Mask token for logging security
        masked_headers = dict(headers)
        if masked_headers.get("X-Dev-Token"):
            masked_headers["X-Dev-Token"] = "***"

        start_time = time.time()
        client = self._get_client()
        owns_client = self._external_client is None

        try:
            resp = client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
            )
            latency_ms = round((time.time() - start_time) * 1000, 2)
            logger.info(
                "Backend call: %s %s -> status=%d latency=%.1fms (auth=%s)",
                method,
                path,
                resp.status_code,
                latency_ms,
                masked_headers["X-Dev-Token"],
            )

            if resp.status_code >= 400:
                raise BackendAPIError(resp.status_code, resp.text)

            return resp.json() if resp.content else {}
        finally:
            if owns_client:
                client.close()

    # Product Endpoints
    def list_products(self, limit: int = 50) -> Dict[str, Any]:
        return self.request("GET", "/products", params={"limit": limit})

    def get_product_state(self, product_id: str) -> Dict[str, Any]:
        return self.request("GET", f"/products/{product_id}/state")

    def create_product(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("POST", "/products", json_data=payload)

    def get_product_events(self, product_id: str, limit: int = 50) -> Dict[str, Any]:
        return self.request("GET", f"/products/{product_id}/events", params={"limit": limit})

    # Task Endpoints
    def create_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("POST", "/tasks", json_data=payload)

    def get_task_state(self, task_id: str) -> Dict[str, Any]:
        return self.request("GET", f"/tasks/{task_id}")

    def patch_task_parameters(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("PATCH", f"/tasks/{task_id}/parameters", json_data=payload)

    def validate_task(self, task_id: str) -> Dict[str, Any]:
        return self.request("POST", f"/tasks/{task_id}/validate")

    def get_task_events(self, task_id: str, limit: int = 50) -> Dict[str, Any]:
        return self.request("GET", f"/tasks/{task_id}/events", params={"limit": limit})

    # Update Proposal Endpoints
    def propose_update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("POST", "/updates", json_data=payload)

    def get_update_state(self, update_id: str) -> Dict[str, Any]:
        return self.request("GET", f"/updates/{update_id}")

    def confirm_update(self, update_id: str, base_product_revision: int) -> Dict[str, Any]:
        return self.request(
            "POST",
            f"/updates/{update_id}/confirm",
            json_data={"base_product_revision": base_product_revision},
        )

    def reject_update(self, update_id: str) -> Dict[str, Any]:
        return self.request("POST", f"/updates/{update_id}/reject")


_default_backend_client: Optional[BackendClient] = None


def get_backend_client() -> BackendClient:
    global _default_backend_client
    if _default_backend_client is None:
        _default_backend_client = BackendClient()
    return _default_backend_client
