import os
from typing import Any, Callable, Dict, Optional
import httpx

from app.solver.errors import (
    RevisionConflictError,
    SolverAPIError,
    SolverValidationError,
)
from app.solver.target_gap import compute

DEFAULT_BACKEND_URL = "https://stock-copilot-backend.onrender.com"


def _get_default_token() -> str:
    """Retrieve development token from environment variable or ISCM .env file."""
    token = os.environ.get("DEV_TOKEN") or os.environ.get("X_DEV_TOKEN")
    if token:
        return token.strip().strip('"').strip("'")

    # Try reading from .env in project root
    env_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("DEV_TOKEN="):
                            raw = line.split("=", 1)[1].strip()
                            return raw.strip('"').strip("'")
            except Exception:
                pass
    return ""


def run_solver(
    task_id: str,
    base_url: str = DEFAULT_BACKEND_URL,
    token: Optional[str] = None,
    client: Optional[httpx.Client] = None,
    on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """
    Executes the solver lifecycle for a given task_id:

    OpenAPI Endpoint Sequencing Analysis:
    --------------------------------------
    According to /openapi.json and the Backend Handoff contract:
    - POST /tasks/{id}/calculate is the server's internal reference calculator.
    - GET /tasks/{id}/calculation-input provides the frozen input snapshot,
      eligible incoming stock, target, and the current product_revision & task_revision.
    - POST /tasks/{id}/result is the designated endpoint for external solvers
      to submit the calculated projected_balance and shortfall with the verified revisions.

    Sequence:
    1. Emit event 'working'.
    2. Loop up to (max_retries + 1) attempts:
       a. Fetch GET /tasks/{id}/calculation-input.
       b. Record product_revision and task_revision.
       c. Compute deterministically via compute(calc_input).
       d. Submit result to POST /tasks/{id}/result.
       e. If HTTP 409 (revision conflict), retry if attempts remain.
    3. Emit event 'done' with final result.
    """
    if not task_id:
        raise SolverValidationError("task_id must be provided.")

    dev_token = token or _get_default_token()
    headers = {
        "X-Dev-Token": dev_token,
        "Content-Type": "application/json",
    }

    def emit(state: str, payload: Dict[str, Any]) -> None:
        if on_event:
            try:
                on_event(state, payload)
            except Exception:
                pass

    emit("working", {"task_id": task_id})

    owns_client = False
    if client is None:
        client = httpx.Client(base_url=base_url, headers=headers, timeout=30.0)
        owns_client = True

    try:
        last_error_detail = ""
        # Total attempts = 1 initial + max_retries
        for attempt in range(max_retries + 1):
            # 1. Fetch calculation-input
            calc_input_url = f"/tasks/{task_id}/calculation-input"
            if not owns_client:
                # If a mock or external client is passed without base_url matching
                resp_input = client.get(calc_input_url)
            else:
                resp_input = client.get(calc_input_url)

            if resp_input.status_code != 200:
                raise SolverAPIError(
                    f"Failed to fetch calculation-input for task {task_id}: "
                    f"HTTP {resp_input.status_code} - {resp_input.text}"
                )

            input_data = resp_input.json()
            product_rev = input_data.get("product_revision")
            task_rev = input_data.get("task_revision")

            if product_rev is None or task_rev is None:
                raise SolverValidationError(
                    f"Missing product_revision or task_revision in calculation-input: {input_data}"
                )

            # 2. Compute deterministically (validates all fields including expected_outgoing_qty)
            computed = compute(input_data)

            # 3. Submit result
            payload = {
                "product_revision": product_rev,
                "task_revision": task_rev,
                "projected_balance": computed["projected_balance"],
                "shortfall": computed["shortfall"],
            }

            result_url = f"/tasks/{task_id}/result"
            resp_result = client.post(result_url, json=payload)

            if resp_result.status_code == 200:
                result_data = resp_result.json()
                emit(
                    "done",
                    {
                        "task_id": task_id,
                        "result": computed,
                        "attempts": attempt + 1,
                        "backend_response": result_data,
                    },
                )
                return result_data

            if resp_result.status_code == 409:
                # Revision changed or conflict
                last_error_detail = resp_result.text
                if attempt < max_retries:
                    # Retry: loop will fetch fresh calculation-input and re-compute
                    continue
                else:
                    raise RevisionConflictError(
                        f"Task {task_id} result submission rejected due to revision conflict "
                        f"after {attempt + 1} attempts. Response: {last_error_detail}"
                    )

            raise SolverAPIError(
                f"Failed to submit result for task {task_id}: "
                f"HTTP {resp_result.status_code} - {resp_result.text}"
            )

        raise RevisionConflictError(
            f"Exceeded max retries ({max_retries}) for task {task_id}. Last error: {last_error_detail}"
        )

    finally:
        if owns_client:
            client.close()
