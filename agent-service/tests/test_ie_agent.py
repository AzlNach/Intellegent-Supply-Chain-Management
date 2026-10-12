import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.backend_client import BackendAPIError, BackendClient
from app.ie_agent import IEAgent, SAFE_FALLBACK_MESSAGE, detect_state_conflicts
from app.main import app
from app.memory import session_memory
from app.tools import TOOL_DEFINITIONS, ToolExecutor


def test_no_confirm_or_reject_or_delete_tools_for_llm():
    # Assert: Tidak ada tool untuk confirm, reject, atau delete.
    tool_names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    for name in tool_names:
        assert "confirm" not in name.lower(), f"Forbidden tool: {name}"
        assert "reject" not in name.lower(), f"Forbidden tool: {name}"
        assert "delete" not in name.lower(), f"Forbidden tool: {name}"


def test_conflict_detection_stock_mismatch_and_stale_and_unverified_eta():
    prod_state = {
        "product_id": "MIE-A",
        "unit": "bungkus",
        "revision": 1,
        "facts": {
            "on_hand_qty": 25,
            # Old stock_as_of from 24 hours ago
            "stock_as_of": "2026-10-09T00:00:00+00:00",
            "incoming_orders": [
                {
                    "order_id": "PO-99",
                    "status": "in_transit",
                    "remaining_qty": 10,
                    "eta_verified_at": None,  # unverified ETA
                    "expected_arrival_at": "2026-10-15T00:00:00+00:00",
                }
            ],
        },
    }

    # User claims stock is 10, deadline is 2026-10-12 (before PO-99 arrival)
    conflicts = detect_state_conflicts(
        prod_state=prod_state,
        claimed_stock=10,
        required_by_str="2026-10-12T00:00:00+00:00",
        freshness_hours=12.0,
    )

    assert len(conflicts) >= 3
    # 1. Stock mismatch
    assert any("Konflik stok" in c for c in conflicts)
    # 2. Stale stock_as_of
    assert any("lebih dari 12.0 jam lalu" in c or "kadaluarsa" in c or "verifikasi stok terkini" in c for c in conflicts)
    # 3. Unverified ETA
    assert any("belum memiliki ETA" in c for c in conflicts)


@pytest.mark.asyncio
async def test_agent_detects_conflict_and_asks_clarification():
    mock_backend = MagicMock(spec=BackendClient)
    mock_backend.get_product_state.return_value = {
        "product_id": "MIE-A",
        "unit": "bungkus",
        "revision": 1,
        "facts": {"on_hand_qty": 25, "stock_as_of": "2026-10-10T12:00:00+00:00"},
    }

    # Mock chat response: LLM clarifies stock conflict
    mock_llm_res = {
        "content": json.dumps({
            "intent": "clarify",
            "extracted": {"product_id": "MIE-A", "on_hand_qty": 10},
            "conflicts": ["Konflik stok: Anda menyebutkan 10, data sistem 25."],
            "next_action": "clarify",
            "message_to_user": "Stok di sistem tercatat 25 bungkus, namun Anda menyebutkan 10. Apakah ada penyesuaian fisik?",
        }),
        "tool_calls": None,
    }

    with patch("app.ie_agent.chat", return_value=mock_llm_res):
        agent = IEAgent(backend_client=mock_backend)
        resp = await agent.run(session_id="sess-conflict-1", user_message="Stok Mie A sisa 10 bungkus")

        assert resp.next_action == "clarify"
        assert len(resp.conflicts) > 0
        assert "25" in resp.message_to_user or "penyesuaian" in resp.message_to_user


@pytest.mark.asyncio
async def test_revision_mismatch_reread_and_retry():
    mock_backend = MagicMock(spec=BackendClient)

    # 1st call fails with 409
    err_409 = BackendAPIError(409, "Revision mismatch")
    success_proposal = {"update_id": "REQ-123", "status": "PENDING"}

    # Mock propose_update: fail first, succeed second
    mock_backend.propose_update.side_effect = [err_409, success_proposal]
    mock_backend.get_product_state.return_value = {
        "product_id": "MIE-A",
        "revision": 2,
    }

    # Tool call for propose_update
    tool_call_obj = MagicMock()
    tool_call_obj.id = "call_prop_1"
    tool_call_obj.function = MagicMock(
        name="propose_update",
        arguments=json.dumps({
            "product_id": "MIE-A",
            "changes": {"facts": {"on_hand_qty": 10}},
            "source_ref": "MSG-01",
            "base_product_revision": 1,
        }),
    )
    tool_call_obj.function.name = "propose_update"

    # LLM responses: 1st yields tool call, 2nd yields final answer
    llm_resp_1 = {
        "content": "",
        "tool_calls": [tool_call_obj],
    }
    llm_resp_2 = {
        "content": json.dumps({
            "intent": "update_stock",
            "extracted": {"product_id": "MIE-A", "on_hand_qty": 10},
            "conflicts": [],
            "next_action": "answer",
            "message_to_user": "Usulan perubahan stok fisik telah diajukan (REQ-123).",
        }),
        "tool_calls": None,
    }

    with patch("app.ie_agent.chat", side_effect=[llm_resp_1, llm_resp_2]):
        agent = IEAgent(backend_client=mock_backend)
        resp = await agent.run(session_id="sess-rev-1", user_message="Perbarui stok Mie A jadi 10")

        # Verify retry happened
        assert mock_backend.propose_update.call_count == 2
        assert resp.next_action == "answer"
        assert "REQ-123" in resp.message_to_user


@pytest.mark.asyncio
async def test_calculation_numbers_originate_only_from_solver():
    mock_backend = MagicMock(spec=BackendClient)
    mock_backend.base_url = "https://stock-copilot-backend.onrender.com"
    mock_backend.token = "dummy-token"

    # Tool call for run_solver
    tool_call_obj = MagicMock()
    tool_call_obj.id = "call_solver_1"
    tool_call_obj.function = MagicMock(
        name="run_solver",
        arguments=json.dumps({"task_id": "TASK-SOLVE-1"}),
    )
    tool_call_obj.function.name = "run_solver"

    llm_resp_1 = {
        "content": "",
        "tool_calls": [tool_call_obj],
    }
    llm_resp_2 = {
        "content": json.dumps({
            "intent": "calculate_gap",
            "extracted": {},
            "conflicts": [],
            "next_action": "answer",
            "message_to_user": "Hasil perhitungan resmi: saldo proyeksi adalah 28 dan kekurangan stok (shortfall) adalah 22 unit.",
        }),
        "tool_calls": None,
    }

    mock_solver_result = {
        "status": "COMPUTED",
        "projected_balance": 28,
        "shortfall": 22,
    }

    with patch("app.ie_agent.chat", side_effect=[llm_resp_1, llm_resp_2]):
        with patch("app.tools.execute_solver", return_value=mock_solver_result) as mock_exec_solver:
            agent = IEAgent(backend_client=mock_backend)
            resp = await agent.run(session_id="sess-solver-1", user_message="Hitung kekurangan stok untuk task TASK-SOLVE-1")

            assert mock_exec_solver.call_count == 1
            # Check numbers match solver return
            assert "28" in resp.message_to_user
            assert "22" in resp.message_to_user


@pytest.mark.asyncio
async def test_invalid_json_handled_with_safe_fallback_message():
    # LLM consistently returns invalid JSON string
    garbage_resp = {
        "content": "Ini bukan format JSON sama sekali! Error...",
        "tool_calls": None,
    }

    with patch("app.ie_agent.chat", return_value=garbage_resp):
        agent = IEAgent()
        resp = await agent.run(session_id="sess-invalid-json", user_message="Halo?")

        assert resp.message_to_user == SAFE_FALLBACK_MESSAGE
        assert resp.next_action == "clarify"


def test_ui_confirm_proposal_endpoint():
    mock_backend = MagicMock(spec=BackendClient)
    mock_backend.get_update_state.return_value = {"update_id": "REQ-10", "product_id": "MIE-A"}
    mock_backend.get_product_state.return_value = {"product_id": "MIE-A", "revision": 3}
    mock_backend.confirm_update.return_value = {"status": "APPROVED", "applied_product_revision": 4}

    with patch("app.main.get_backend_client", return_value=mock_backend):
        client = TestClient(app)
        res = client.post("/proposals/REQ-10/confirm")
        assert res.status_code == 200
        assert res.json()["status"] == "APPROVED"
        # Checked that confirm_update was called with latest revision 3
        mock_backend.confirm_update.assert_called_once_with(update_id="REQ-10", base_product_revision=3)


def test_ui_reject_proposal_endpoint():
    mock_backend = MagicMock(spec=BackendClient)
    mock_backend.reject_update.return_value = {"status": "REJECTED"}

    with patch("app.main.get_backend_client", return_value=mock_backend):
        client = TestClient(app)
        res = client.post("/proposals/REQ-10/reject")
        assert res.status_code == 200
        assert res.json()["status"] == "REJECTED"
        mock_backend.reject_update.assert_called_once_with(update_id="REQ-10")


def test_chat_endpoint_via_http():
    mock_agent_response = {
        "intent": "inquiry",
        "extracted": {"product_id": "MIE-A"},
        "conflicts": [],
        "next_action": "answer",
        "message_to_user": "Stok Mie A saat ini tersedia 25 bungkus.",
    }

    with patch("app.ie_agent.IEAgent.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_agent_response
        client = TestClient(app)
        res = client.post("/chat", json={"session_id": "test-sess", "message": "Berapa stok Mie A?"})
        assert res.status_code == 200
        assert res.json()["intent"] == "inquiry"
        assert "25" in res.json()["message_to_user"]


def test_websocket_connection_and_broadcast():
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text("ping")
        # websocket is connected


def test_tool_executor_dispatches_properly():
    mock_backend = MagicMock(spec=BackendClient)
    mock_backend.list_products.return_value = {"items": []}
    mock_backend.get_product_state.return_value = {"product_id": "P1", "revision": 1}
    mock_backend.create_product.return_value = {"product_id": "P1"}
    mock_backend.create_task.return_value = {"task_id": "T1"}
    mock_backend.get_task_state.return_value = {"task_id": "T1"}
    mock_backend.patch_task_parameters.return_value = {"task_id": "T1", "revision": 2}
    mock_backend.validate_task.return_value = {"ready": True}
    mock_backend.get_update_state.return_value = {"update_id": "U1"}

    executor = ToolExecutor(backend_client=mock_backend)

    assert executor.dispatch("list_products", {"limit": 10}) == {"items": []}
    assert executor.dispatch("get_product_state", {"product_id": "P1"}) == {"product_id": "P1", "revision": 1}
    assert executor.dispatch("create_product", {
        "product_id": "P1", "name": "Item 1", "unit": "pcs", "on_hand_qty": 10, "target_qty": 20
    }) == {"product_id": "P1"}
    assert executor.dispatch("create_task", {"product_id": "P1"}) == {"task_id": "T1"}
    assert executor.dispatch("get_task_state", {"task_id": "T1"}) == {"task_id": "T1"}
    assert executor.dispatch("patch_task_parameters", {"task_id": "T1", "base_task_revision": 1}) == {"task_id": "T1", "revision": 2}
    assert executor.dispatch("validate_task", {"task_id": "T1"}) == {"ready": True}
    assert executor.dispatch("get_update_state", {"update_id": "U1"}) == {"update_id": "U1"}

    with pytest.raises(ValueError):
        executor.dispatch("unknown_tool", {})

