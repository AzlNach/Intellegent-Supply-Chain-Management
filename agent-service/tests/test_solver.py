import pytest
from unittest.mock import MagicMock, call
import httpx

from app.solver import compute, TargetGapSolver, Solver
from app.solver.errors import SolverValidationError, RevisionConflictError
from app.solver.runner import run_solver


def test_base_solver_interface():
    assert issubclass(TargetGapSolver, Solver)
    solver = TargetGapSolver()
    result = solver.solve({
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    })
    assert result == {"projected_balance": 28, "shortfall": 22}


def test_compute_case_1():
    # on_hand 25, incoming 15, outgoing 12, target 50 -> balance 28, shortfall 22
    calc_input = {
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    }
    result = compute(calc_input)
    assert result["projected_balance"] == 28
    assert result["shortfall"] == 22


def test_compute_case_2():
    # on_hand 60, incoming 0, outgoing 10, target 50 -> balance 50, shortfall 0
    calc_input = {
        "on_hand_qty": 60,
        "eligible_incoming_qty": 0,
        "expected_outgoing_qty": 10,
        "target_qty": 50,
    }
    result = compute(calc_input)
    assert result["projected_balance"] == 50
    assert result["shortfall"] == 0


def test_compute_case_3():
    # on_hand 5, incoming 0, outgoing 12, target 50 -> balance -7, shortfall 57
    calc_input = {
        "on_hand_qty": 5,
        "eligible_incoming_qty": 0,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    }
    result = compute(calc_input)
    assert result["projected_balance"] == -7
    assert result["shortfall"] == 57


def test_compute_does_not_resum_included_orders():
    # Gunakan eligible_incoming_qty apa adanya. Jangan menjumlah ulang included_orders.
    calc_input = {
        "on_hand_qty": 20,
        "eligible_incoming_qty": 10,
        "expected_outgoing_qty": 5,
        "target_qty": 30,
        "included_orders": [
            {"order_id": "ORD-1", "remaining_qty": 999},
            {"order_id": "ORD-2", "remaining_qty": 888},
        ],
    }
    result = compute(calc_input)
    # 20 + 10 - 5 = 25; max(0, 30 - 25) = 5
    assert result["projected_balance"] == 25
    assert result["shortfall"] == 5


@pytest.mark.parametrize("missing_field", [
    "expected_outgoing_qty",
    "on_hand_qty",
    "eligible_incoming_qty",
    "target_qty",
])
def test_validation_missing_or_none_fields_raise_error(missing_field):
    base_input = {
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    }
    # Test None
    invalid_input = dict(base_input)
    invalid_input[missing_field] = None
    with pytest.raises(SolverValidationError) as excinfo:
        compute(invalid_input)
    assert missing_field in str(excinfo.value)

    # Test key omitted
    invalid_input_omitted = dict(base_input)
    del invalid_input_omitted[missing_field]
    with pytest.raises(SolverValidationError) as excinfo_omitted:
        compute(invalid_input_omitted)
    assert missing_field in str(excinfo_omitted.value)


@pytest.mark.parametrize("invalid_val", ["12", 12.5, True, False, []])
def test_validation_non_integer_type_raises_error(invalid_val):
    calc_input = {
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": invalid_val,
        "target_qty": 50,
    }
    with pytest.raises(SolverValidationError):
        compute(calc_input)


def test_run_solver_empty_outgoing_fails_without_result_call():
    # Nilai kosong menghasilkan galat tanpa panggilan result.
    mock_client = MagicMock(spec=httpx.Client)

    # calculation-input returns expected_outgoing_qty = None
    mock_calc_input_resp = MagicMock(spec=httpx.Response)
    mock_calc_input_resp.status_code = 200
    mock_calc_input_resp.json.return_value = {
        "task_id": "TASK-1",
        "product_revision": 1,
        "task_revision": 1,
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": None,
        "target_qty": 50,
    }
    mock_client.get.return_value = mock_calc_input_resp

    event_log = []
    def on_event(state, data):
        event_log.append((state, data))

    with pytest.raises(SolverValidationError):
        run_solver("TASK-1", client=mock_client, on_event=on_event)

    # Ensure client.post was NEVER called for /result
    assert mock_client.post.call_count == 0
    # Ensure working state was sent, but not done
    assert ("working", {"task_id": "TASK-1"}) in event_log
    assert not any(state == "done" for state, _ in event_log)


def test_run_solver_retry_on_revision_conflict_then_success():
    # Revisi ditolak lalu berhasil pada percobaan kedua.
    mock_client = MagicMock(spec=httpx.Client)

    # First attempt: calculation-input has rev p1, t1
    resp_calc_1 = MagicMock(spec=httpx.Response)
    resp_calc_1.status_code = 200
    resp_calc_1.json.return_value = {
        "task_id": "TASK-1",
        "product_revision": 1,
        "task_revision": 1,
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    }

    # Second attempt: calculation-input has rev p2, t2
    resp_calc_2 = MagicMock(spec=httpx.Response)
    resp_calc_2.status_code = 200
    resp_calc_2.json.return_value = {
        "task_id": "TASK-1",
        "product_revision": 2,
        "task_revision": 2,
        "on_hand_qty": 30,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    }

    mock_client.get.side_effect = [resp_calc_1, resp_calc_2]

    # First submit result: 409 Conflict
    resp_post_1 = MagicMock(spec=httpx.Response)
    resp_post_1.status_code = 409
    resp_post_1.json.return_value = {"detail": "Revision changed"}

    # Second submit result: 200 OK
    resp_post_2 = MagicMock(spec=httpx.Response)
    resp_post_2.status_code = 200
    resp_post_2.json.return_value = {
        "status": "COMPUTED",
        "projected_balance": 33,
        "shortfall": 17,
    }

    mock_client.post.side_effect = [resp_post_1, resp_post_2]

    event_log = []
    def on_event(state, data):
        event_log.append((state, data))

    final_result = run_solver("TASK-1", client=mock_client, on_event=on_event, max_retries=2)

    assert mock_client.get.call_count == 2
    assert mock_client.post.call_count == 2

    # Check first POST payload used rev 1, 1
    call1_payload = mock_client.post.call_args_list[0][1]["json"]
    assert call1_payload["product_revision"] == 1
    assert call1_payload["task_revision"] == 1
    assert call1_payload["projected_balance"] == 28
    assert call1_payload["shortfall"] == 22

    # Check second POST payload used rev 2, 2 and recomputed with on_hand 30
    # 30 + 15 - 12 = 33, max(0, 50 - 33) = 17
    call2_payload = mock_client.post.call_args_list[1][1]["json"]
    assert call2_payload["product_revision"] == 2
    assert call2_payload["task_revision"] == 2
    assert call2_payload["projected_balance"] == 33
    assert call2_payload["shortfall"] == 17

    # Check events: working -> done
    states = [s for s, _ in event_log]
    assert states == ["working", "done"]
    done_data = event_log[1][1]
    assert done_data["task_id"] == "TASK-1"
    assert done_data["result"]["projected_balance"] == 33
    assert done_data["result"]["shortfall"] == 17
    assert final_result["status"] == "COMPUTED"


def test_run_solver_max_retries_exceeded():
    mock_client = MagicMock(spec=httpx.Client)

    resp_calc = MagicMock(spec=httpx.Response)
    resp_calc.status_code = 200
    resp_calc.json.return_value = {
        "task_id": "TASK-1",
        "product_revision": 1,
        "task_revision": 1,
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    }
    mock_client.get.return_value = resp_calc

    # Always 409 Conflict
    resp_post = MagicMock(spec=httpx.Response)
    resp_post.status_code = 409
    resp_post.json.return_value = {"detail": "Conflict"}
    mock_client.post.return_value = resp_post

    with pytest.raises(RevisionConflictError):
        run_solver("TASK-1", client=mock_client, max_retries=2)

    # 1 initial + 2 retries = 3 calls
    assert mock_client.post.call_count == 3


def test_run_solver_empty_task_id_raises_error():
    with pytest.raises(SolverValidationError):
        run_solver("")


def test_run_solver_calc_input_http_error():
    mock_client = MagicMock(spec=httpx.Client)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    resp.text = "Task not found"
    mock_client.get.return_value = resp

    from app.solver.errors import SolverAPIError
    with pytest.raises(SolverAPIError) as excinfo:
        run_solver("TASK-NONEXISTENT", client=mock_client)
    assert "404" in str(excinfo.value)


def test_run_solver_missing_revision_in_calc_input():
    mock_client = MagicMock(spec=httpx.Client)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {
        "task_id": "TASK-1",
        # product_revision omitted
        "task_revision": 1,
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    }
    mock_client.get.return_value = resp

    with pytest.raises(SolverValidationError):
        run_solver("TASK-1", client=mock_client)


def test_run_solver_submit_result_500_error():
    mock_client = MagicMock(spec=httpx.Client)
    resp_calc = MagicMock(spec=httpx.Response)
    resp_calc.status_code = 200
    resp_calc.json.return_value = {
        "task_id": "TASK-1",
        "product_revision": 1,
        "task_revision": 1,
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    }
    mock_client.get.return_value = resp_calc

    resp_post = MagicMock(spec=httpx.Response)
    resp_post.status_code = 500
    resp_post.text = "Internal Server Error"
    mock_client.post.return_value = resp_post

    from app.solver.errors import SolverAPIError
    with pytest.raises(SolverAPIError) as excinfo:
        run_solver("TASK-1", client=mock_client)
    assert "500" in str(excinfo.value)


def test_compute_non_dict_input():
    with pytest.raises(SolverValidationError):
        compute(["not", "a", "dict"])


def test_on_event_exception_handled():
    mock_client = MagicMock(spec=httpx.Client)
    resp_calc = MagicMock(spec=httpx.Response)
    resp_calc.status_code = 200
    resp_calc.json.return_value = {
        "task_id": "TASK-1",
        "product_revision": 1,
        "task_revision": 1,
        "on_hand_qty": 25,
        "eligible_incoming_qty": 15,
        "expected_outgoing_qty": 12,
        "target_qty": 50,
    }
    mock_client.get.return_value = resp_calc

    resp_post = MagicMock(spec=httpx.Response)
    resp_post.status_code = 200
    resp_post.json.return_value = {"status": "COMPUTED"}
    mock_client.post.return_value = resp_post

    def bad_listener(state, data):
        raise RuntimeError("listener crash")

    # Should not raise RuntimeError from listener
    result = run_solver("TASK-1", client=mock_client, on_event=bad_listener)
    assert result == {"status": "COMPUTED"}

