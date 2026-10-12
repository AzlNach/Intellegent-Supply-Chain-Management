from typing import Any, Dict

from app.solver.base import Solver
from app.solver.errors import SolverValidationError

REQUIRED_FIELDS = (
    "on_hand_qty",
    "eligible_incoming_qty",
    "expected_outgoing_qty",
    "target_qty",
)


def compute(calc_input: Dict[str, Any]) -> Dict[str, int]:
    """
    Pure function that accepts fields from GET /tasks/{id}/calculation-input
    and computes projected_balance and shortfall deterministically without LLM.

    Formula:
      projected_balance = on_hand_qty + eligible_incoming_qty - expected_outgoing_qty
      shortfall = max(0, target_qty - projected_balance)

    Note:
      Uses eligible_incoming_qty as-is. Does NOT re-sum included_orders.
    """
    if not isinstance(calc_input, dict):
        raise SolverValidationError(f"calc_input must be a dictionary, got {type(calc_input).__name__}")

    # Validate all required fields
    for field in REQUIRED_FIELDS:
        if field not in calc_input or calc_input[field] is None:
            raise SolverValidationError(
                f"Field '{field}' is required and cannot be empty or null."
            )

        val = calc_input[field]
        # In Python, bool is a subclass of int (True == 1, False == 0), so explicitly exclude bool
        if not isinstance(val, int) or isinstance(val, bool):
            raise SolverValidationError(
                f"Field '{field}' must be an integer, got {type(val).__name__} ({val!r})."
            )

    on_hand_qty = calc_input["on_hand_qty"]
    eligible_incoming_qty = calc_input["eligible_incoming_qty"]
    expected_outgoing_qty = calc_input["expected_outgoing_qty"]
    target_qty = calc_input["target_qty"]

    projected_balance = on_hand_qty + eligible_incoming_qty - expected_outgoing_qty
    shortfall = max(0, target_qty - projected_balance)

    return {
        "projected_balance": projected_balance,
        "shortfall": shortfall,
    }


class TargetGapSolver(Solver):
    """Deterministic solver for target gap inventory operation."""

    def solve(self, calc_input: Dict[str, Any]) -> Dict[str, int]:
        return compute(calc_input)
