import datetime
import uuid
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from app.backend_client import BackendClient, get_backend_client
from app.solver.runner import run_solver as execute_solver


# Pydantic Schemas for Tool Inputs
class ListProductsInput(BaseModel):
    limit: int = Field(50, ge=1, le=100, description="Max products to return")


class GetProductStateInput(BaseModel):
    product_id: str = Field(..., description="ID of the product to inspect")


class CreateProductInput(BaseModel):
    product_id: str = Field(..., description="Unique product ID")
    name: str = Field(..., description="Product name")
    unit: str = Field(..., description="Stock unit e.g. bungkus, karton, kg")
    on_hand_qty: int = Field(..., ge=0, description="Current stock on hand")
    target_qty: int = Field(..., ge=0, description="Target minimum stock")
    stock_source: str = Field("initial_setup", description="Source of initial stock count")
    target_source: str = Field("owner_policy", description="Source of target policy")


class ProposeUpdateInput(BaseModel):
    product_id: str = Field(..., description="Product ID being modified")
    changes: Dict[str, Any] = Field(..., description="Dictionary of changes to facts or policy")
    source_ref: str = Field(..., description="Chat message ID or human reference as basis of update")
    request_id: Optional[str] = Field(None, description="Optional unique request ID")
    task_id: Optional[str] = Field(None, description="Optional task ID linked to this proposal")
    base_product_revision: Optional[int] = Field(None, description="Base revision of the product")


class GetUpdateStateInput(BaseModel):
    update_id: str = Field(..., description="Update proposal ID")


# TODO: Move create_task to Manager agent once Manager agent is implemented in v2
class CreateTaskInput(BaseModel):
    product_id: str = Field(..., description="Target product ID for target_gap task")
    expected_outgoing_qty: Optional[int] = Field(None, ge=0, description="Estimated outgoing demand")
    required_by: Optional[str] = Field(None, description="ISO datetime string deadline")
    target_qty: Optional[int] = Field(None, ge=0, description="Override target quantity")


class GetTaskStateInput(BaseModel):
    task_id: str = Field(..., description="Task ID to inspect")


class PatchTaskParametersInput(BaseModel):
    task_id: str = Field(..., description="Task ID to update")
    base_task_revision: int = Field(..., ge=1, description="Current revision of task")
    expected_outgoing_qty: Optional[int] = Field(None, ge=0, description="Estimated outgoing demand")
    required_by: Optional[str] = Field(None, description="ISO datetime string deadline")
    target_qty: Optional[int] = Field(None, ge=0, description="Override target quantity")


class ValidateTaskInput(BaseModel):
    task_id: str = Field(..., description="Task ID to validate")


class RunSolverInput(BaseModel):
    task_id: str = Field(..., description="Validated task ID to calculate and solve")


class ToolExecutor:
    """Dispatches tool calls with Pydantic validation and backend communication."""

    def __init__(self, backend_client: Optional[BackendClient] = None):
        self.backend = backend_client or get_backend_client()

    def list_products(self, **kwargs) -> Dict[str, Any]:
        data = ListProductsInput(**kwargs)
        return self.backend.list_products(limit=data.limit)

    def get_product_state(self, **kwargs) -> Dict[str, Any]:
        data = GetProductStateInput(**kwargs)
        return self.backend.get_product_state(product_id=data.product_id)

    def create_product(self, **kwargs) -> Dict[str, Any]:
        data = CreateProductInput(**kwargs)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload = {
            "product_id": data.product_id,
            "name": data.name,
            "unit": data.unit,
            "facts": {
                "on_hand_qty": data.on_hand_qty,
                "stock_as_of": now_iso,
                "stock_source": data.stock_source,
                "incoming_orders": [],
                "incoming_checked_at": now_iso,
                "incoming_source": "initial_setup",
            },
            "policy": {
                "target_qty": data.target_qty,
                "source": data.target_source,
            },
        }
        return self.backend.create_product(payload)

    def propose_update(self, **kwargs) -> Dict[str, Any]:
        data = ProposeUpdateInput(**kwargs)
        # Fetch current product revision if not provided
        base_rev = data.base_product_revision
        if base_rev is None:
            prod_state = self.backend.get_product_state(data.product_id)
            base_rev = prod_state.get("revision", 1)

        req_id = data.request_id or f"REQ-{uuid.uuid4().hex[:8].upper()}"
        payload = {
            "product_id": data.product_id,
            "base_product_revision": base_rev,
            "task_id": data.task_id,
            "request_id": req_id,
            "source_ref": data.source_ref,
            "changes": data.changes,
        }
        return self.backend.propose_update(payload)

    def get_update_state(self, **kwargs) -> Dict[str, Any]:
        data = GetUpdateStateInput(**kwargs)
        return self.backend.get_update_state(update_id=data.update_id)

    # TODO: Move create_task to Manager agent
    def create_task(self, **kwargs) -> Dict[str, Any]:
        data = CreateTaskInput(**kwargs)
        payload = {
            "product_id": data.product_id,
            "expected_outgoing_qty": data.expected_outgoing_qty,
            "required_by": data.required_by,
            "target_qty": data.target_qty,
        }
        return self.backend.create_task(payload)

    def get_task_state(self, **kwargs) -> Dict[str, Any]:
        data = GetTaskStateInput(**kwargs)
        return self.backend.get_task_state(task_id=data.task_id)

    def patch_task_parameters(self, **kwargs) -> Dict[str, Any]:
        data = PatchTaskParametersInput(**kwargs)
        payload = {
            "base_task_revision": data.base_task_revision,
            "expected_outgoing_qty": data.expected_outgoing_qty,
            "required_by": data.required_by,
            "target_qty": data.target_qty,
        }
        return self.backend.patch_task_parameters(task_id=data.task_id, payload=payload)

    def validate_task(self, **kwargs) -> Dict[str, Any]:
        data = ValidateTaskInput(**kwargs)
        return self.backend.validate_task(task_id=data.task_id)

    def run_solver(self, **kwargs) -> Dict[str, Any]:
        data = RunSolverInput(**kwargs)
        base_url = getattr(self.backend, "base_url", None)
        token = getattr(self.backend, "token", None)
        # Directly executes deterministic solver engine
        return execute_solver(
            task_id=data.task_id,
            base_url=base_url or "https://stock-copilot-backend.onrender.com",
            token=token,
        )

    def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        handlers: Dict[str, Callable] = {
            "list_products": self.list_products,
            "get_product_state": self.get_product_state,
            "create_product": self.create_product,
            "propose_update": self.propose_update,
            "get_update_state": self.get_update_state,
            "create_task": self.create_task,
            "get_task_state": self.get_task_state,
            "patch_task_parameters": self.patch_task_parameters,
            "validate_task": self.validate_task,
            "run_solver": self.run_solver,
        }
        if tool_name not in handlers:
            raise ValueError(f"Unknown tool '{tool_name}' or unauthorized tool call.")
        return handlers[tool_name](**arguments)


# OpenAI Function Calling Schemas (Confirm, Reject, Delete are explicitly omitted)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "List all products in store",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max products to return"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_state",
            "description": "Get current state, facts, stock on hand, and policy of a product",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID"}
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_product",
            "description": "Add a new product to store",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "name": {"type": "string"},
                    "unit": {"type": "string"},
                    "on_hand_qty": {"type": "integer"},
                    "target_qty": {"type": "integer"},
                },
                "required": ["product_id", "name", "unit", "on_hand_qty", "target_qty"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update",
            "description": "Propose an update to product facts or policy when user declares new verified information",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "changes": {"type": "object", "description": "Changed fields in facts or policy"},
                    "source_ref": {"type": "string", "description": "Chat message ID or user statement reference"},
                    "task_id": {"type": "string", "description": "Optional associated task ID"},
                },
                "required": ["product_id", "changes", "source_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_update_state",
            "description": "Check status of proposed update (PENDING, APPROVED, REJECTED)",
            "parameters": {
                "type": "object",
                "properties": {
                    "update_id": {"type": "string"}
                },
                "required": ["update_id"],
            },
        },
    },
    # TODO: Move create_task to Manager agent
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a target_gap calculation task (Temporary v1 until Manager agent is ready)",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "expected_outgoing_qty": {"type": "integer"},
                    "required_by": {"type": "string", "description": "ISO timestamp deadline"},
                    "target_qty": {"type": "integer"},
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_state",
            "description": "Get state, parameters, revision and status of a task",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"}
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "patch_task_parameters",
            "description": "Update or correct task parameters (expected_outgoing_qty, target_qty, required_by)",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "base_task_revision": {"type": "integer"},
                    "expected_outgoing_qty": {"type": "integer"},
                    "required_by": {"type": "string"},
                    "target_qty": {"type": "integer"},
                },
                "required": ["task_id", "base_task_revision"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_task",
            "description": "Trigger validation for task parameters and readiness",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"}
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_solver",
            "description": "Execute deterministic calculation solver engine once task status is READY without conflicts",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"}
                },
                "required": ["task_id"],
            },
        },
    },
]
