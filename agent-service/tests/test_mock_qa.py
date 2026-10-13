"""Fast deterministic mock-mode acceptance and contract tests."""
import asyncio
import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.backend_client import BackendAPIError, BackendClient
from app.events import ConnectionManager
from app.ie_agent import AgentResponse, IEAgent, SAFE_FALLBACK_MESSAGE, detect_state_conflicts
from app.main import app
from app.memory import SessionState, session_memory
from app.solver import compute
from app.solver.errors import RevisionConflictError, SolverValidationError
from app.solver.runner import run_solver
from app.tools import TOOL_DEFINITIONS
from app.llm_client import LLMClient


@pytest.mark.mock
@pytest.mark.parametrize(
    ("on_hand", "incoming", "outgoing", "target", "balance", "shortfall"),
    [(25, 15, 12, 50, 28, 22), (60, 0, 10, 50, 50, 0), (5, 0, 12, 50, -7, 57)],
)
def test_solver_contract(on_hand, incoming, outgoing, target, balance, shortfall):
    result = compute({
        "on_hand_qty": on_hand,
        "eligible_incoming_qty": incoming,
        "expected_outgoing_qty": outgoing,
        "target_qty": target,
        "included_orders": [{"remaining_qty": 9999}],
    })
    assert result == {"projected_balance": balance, "shortfall": shortfall}


@pytest.mark.mock
def test_solver_null_outgoing_fails_without_result_submission():
    client = MagicMock()
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "product_revision": 1, "task_revision": 1, "on_hand_qty": 25,
        "eligible_incoming_qty": 15, "expected_outgoing_qty": None, "target_qty": 50,
    }
    client.get.return_value = response
    with pytest.raises(SolverValidationError, match="expected_outgoing_qty"):
        run_solver("TEST-VO-MOCK-TASK", client=client)
    client.post.assert_not_called()


@pytest.mark.mock
def test_solver_revision_conflict_retries_twice_then_succeeds():
    client = MagicMock()
    def input_response(product_rev, task_rev, hand):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "product_revision": product_rev, "task_revision": task_rev,
            "on_hand_qty": hand, "eligible_incoming_qty": 15,
            "expected_outgoing_qty": 12, "target_qty": 50,
        }
        return response
    client.get.side_effect = [input_response(1, 1, 25), input_response(2, 2, 30), input_response(3, 3, 35)]
    conflict = MagicMock(status_code=409, text="revision conflict")
    success = MagicMock(status_code=200, text="")
    success.json.return_value = {"status": "COMPUTED", "projected_balance": 38, "shortfall": 12}
    client.post.side_effect = [conflict, conflict, success]
    result = run_solver("TEST-VO-MOCK-TASK", client=client, max_retries=2)
    assert result["status"] == "COMPUTED"
    assert client.get.call_count == 3
    assert client.post.call_count == 3
    assert client.post.call_args.kwargs["json"]["product_revision"] == 3


@pytest.mark.mock
def test_tool_surface_excludes_confirm_reject_delete_and_includes_required_tools():
    names = {tool["function"]["name"] for tool in TOOL_DEFINITIONS}
    assert names == {
        "list_products", "get_product_state", "create_product", "propose_update", "get_update_state",
        "create_task", "get_task_state", "patch_task_parameters", "validate_task", "run_solver",
    }
    assert not any(name in {"confirm", "reject", "delete"} or name.endswith(("_confirm", "_reject", "_delete")) for name in names)


@pytest.mark.mock
def test_backend_logs_mask_authorization_value(caplog):
    client = MagicMock()
    response = MagicMock(status_code=200, content=b'{"ok":true}')
    response.json.return_value = {"ok": True}
    client.request.return_value = response
    secret = "test-vo-secret-never-log"
    backend = BackendClient(base_url="http://mock.invalid", token=secret, client=client)
    with caplog.at_level("INFO", logger="backend_client"):
        backend.list_products()
    assert secret not in caplog.text
    assert "***" in caplog.text


@pytest.mark.mock
def test_agent_invalid_json_retries_once_then_safe_message():
    responses = [
        {"content": "not json", "tool_calls": None},
        {"content": "still not json", "tool_calls": None},
    ]
    with patch("app.ie_agent.chat", side_effect=responses) as llm:
        agent = IEAgent(max_tool_calls=1)
        result = asyncio.run(agent.run("TEST-VO-MOCK-JSON", "Cek stok"))
    assert llm.call_count == 2
    assert result.message_to_user == SAFE_FALLBACK_MESSAGE


@pytest.mark.mock
def test_agent_does_not_offer_confirm_or_reject_tool_calls():
    names = [tool["function"]["name"] for tool in TOOL_DEFINITIONS]
    assert "confirm_update" not in names and "reject_update" not in names
    assert not any("confirm" in name or "reject" in name for name in names)


@pytest.mark.mock
def test_agent_conflicting_stock_claim_requires_clarification_before_writes():
    backend = MagicMock(spec=BackendClient)
    backend.get_product_state.return_value = {
        "product_id": "TEST-VO-MOCK-PRODUCT", "unit": "bungkus", "revision": 1,
        "facts": {"on_hand_qty": 25, "stock_as_of": "2026-10-10T00:00:00+00:00", "incoming_orders": []},
    }
    structured = {
        "intent": "clarify", "extracted": {"product_id": "TEST-VO-MOCK-PRODUCT", "on_hand_qty": 12},
        "conflicts": ["Stok yang disebut berbeda dari database."], "next_action": "clarify",
        "message_to_user": "Database mencatat 25 bungkus, Anda menyebut 12. Mana yang benar?",
    }
    with patch("app.ie_agent.chat", return_value={"content": json.dumps(structured), "tool_calls": None}):
        result = asyncio.run(IEAgent(backend_client=backend).run("TEST-VO-MOCK-CONFLICT", "Stok tinggal 12"))
    assert result.next_action == "clarify"
    backend.propose_update.assert_not_called()
    backend.confirm_update.assert_not_called()


@pytest.mark.mock
def test_event_contract_shape_and_disconnect_recovery():
    class Socket:
        def __init__(self): self.events = []
        async def accept(self): pass
        async def send_text(self, text): self.events.append(json.loads(text))

    manager = ConnectionManager()
    socket = Socket()
    async def exercise():
        await manager.connect(socket)
        await manager.emit_agent_state("working", "TEST-VO-SESSION", {"phase": "solver"})
        await manager.emit_board_update("TEST-VO-SESSION", {"parameters": {}})
        await manager.emit_chat_message("TEST-VO-SESSION", "assistant", "Memproses")
        await manager.emit_proposal_created("TEST-VO-SESSION", {"update_id": "TEST-VO-UPDATE"})
        manager.disconnect(socket)
    asyncio.run(exercise())
    assert [event["type"] for event in socket.events] == ["agent_state", "board_update", "chat_message", "proposal_created"]
    assert socket.events[0]["state"] == "working"
    assert socket.events[2]["content"] == "Memproses"


@pytest.mark.mock
def test_local_health_routes_and_websocket_endpoint():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    with client.websocket_connect("/ws/TEST-VO-SESSION") as websocket:
        websocket.send_text("keepalive")


@pytest.mark.mock
def test_out_of_topic_redirects_without_tool_call():
    backend = MagicMock(spec=BackendClient)
    response = {"intent": "redirect", "extracted": {}, "conflicts": [], "next_action": "answer",
                "message_to_user": "Saya membantu data stok dan kebutuhan inventaris. Ada produk yang ingin dicek?"}
    with patch("app.ie_agent.chat", return_value={"content": json.dumps(response), "tool_calls": None}) as llm:
        result = asyncio.run(IEAgent(backend_client=backend).run("TEST-VO-MOCK-OOT", "Ceritakan sejarah Romawi"))
    assert result.next_action == "answer"
    assert llm.call_count == 1
    backend.list_products.assert_not_called()
    backend.create_task.assert_not_called()


@pytest.mark.mock
def test_stock_conflict_detection_and_staleness_are_deterministic():
    conflicts = detect_state_conflicts(
        {"product_id": "TEST-VO-MOCK", "unit": "bungkus", "facts": {
            "on_hand_qty": 25,
            "stock_as_of": "2020-01-01T00:00:00+00:00",
            "incoming_orders": [{"order_id": "PO-1", "eta_verified_at": None}],
        }},
        claimed_stock=10,
        freshness_hours=12,
    )
    assert any("Konflik stok" in value for value in conflicts)
    assert any("verifikasi stok terkini" in value for value in conflicts)
    assert any("ETA" in value for value in conflicts)


@pytest.mark.mock
def test_clarification_limit_keeps_session_active_without_counter_growth():
    clarification = {"intent": "clarify", "extracted": {}, "conflicts": [], "next_action": "clarify",
                    "message_to_user": "Produk yang mana?"}
    with patch("app.ie_agent.chat", return_value={"content": json.dumps(clarification), "tool_calls": None}) as llm:
        agent = IEAgent(max_clarification_turns=2)
        asyncio.run(agent.run("TEST-VO-MOCK-LIMIT", "Hitung kebutuhan"))
        asyncio.run(agent.run("TEST-VO-MOCK-LIMIT", "Masih belum jelas"))
        final = asyncio.run(agent.run("TEST-VO-MOCK-LIMIT", "Tetap tidak ada nama"))
    session = session_memory.get_or_create("TEST-VO-MOCK-LIMIT")
    assert final.message_to_user == "Produk yang mana?"
    assert session.clarification_turns == 2
    assert llm.call_count == 3, "session should remain active after clarification limit"


@pytest.mark.mock
def test_solver_result_numbers_must_not_be_replaced_by_llm_numbers():
    backend = MagicMock(spec=BackendClient)
    backend.base_url = "https://stock-copilot-backend.onrender.com"
    backend.token = "mock-secret"
    call_tool = MagicMock()
    call_tool.id = "call_solver"
    call_tool.function = MagicMock()
    call_tool.function.name = "run_solver"
    call_tool.function.arguments = json.dumps({"task_id": "TEST-VO-MOCK-TASK"})
    tool_answer = {"content": "", "tool_calls": [call_tool]}
    hallucinated = {"content": json.dumps({"intent": "calculate_gap", "extracted": {}, "conflicts": [],
        "next_action": "answer", "message_to_user": "Projected balance 999 dan shortfall 888."}), "tool_calls": None}
    solver_result = {"status": "COMPUTED", "projected_balance": 28, "shortfall": 22}
    with patch("app.ie_agent.chat", side_effect=[tool_answer, hallucinated]):
        with patch("app.tools.execute_solver", return_value=solver_result):
            answer = asyncio.run(IEAgent(backend_client=backend).run("TEST-VO-MOCK-NUMBERS", "Hitung task"))
    assert "999" not in answer.message_to_user and "888" not in answer.message_to_user
    assert "28" in answer.message_to_user and "22" in answer.message_to_user


@pytest.mark.mock
def test_llm_call_logs_role_model_tokens_and_latency(caplog):
    mock_client = MagicMock()
    completion = MagicMock()
    completion.model = "test-model"
    completion.choices = [MagicMock(message=MagicMock(content="ok", tool_calls=None))]
    completion.usage = MagicMock(prompt_tokens=4, completion_tokens=2, total_tokens=6)
    mock_client.chat.completions.create.return_value = completion
    llm = LLMClient.__new__(LLMClient)
    llm.base_url = "http://mock"
    llm.api_key = "never-log-this"
    llm.client = mock_client
    llm.roles_config = {"ie_agent": {"enabled": True, "model": "test-model", "temperature": 0, "max_tokens": 10, "timeout": 2}}
    llm.supports_tools = {"ie_agent": True}
    llm.max_retries = 0
    llm.initial_backoff = 0
    with caplog.at_level(logging.INFO, logger="llm_client"):
        llm.chat("ie_agent", [{"role": "user", "content": "nonsecret text"}])
    assert "role='ie_agent'" in caplog.text and "model='test-model'" in caplog.text
    assert "prompt_tokens" in caplog.text and "total_tokens" in caplog.text and "latency_ms" in caplog.text
    assert "never-log-this" not in caplog.text


@pytest.mark.mock
def test_llm_uses_configured_fallback_after_primary_server_error():
    from openai import InternalServerError

    mock_client = MagicMock()
    failure = InternalServerError(message="upstream busy", response=MagicMock(status_code=503, headers={}), body=None)
    response = MagicMock()
    response.model = "fallback-model"
    response.choices = [MagicMock(message=MagicMock(content="jawaban", tool_calls=None))]
    response.usage = MagicMock(prompt_tokens=3, completion_tokens=2, total_tokens=5)
    mock_client.chat.completions.create.side_effect = [failure, response]

    llm = LLMClient.__new__(LLMClient)
    llm.client = mock_client
    llm.config_path = "models.yaml"
    llm.roles_config = {"ie_agent": {
        "enabled": True, "model": "primary-model", "fallback_models": ["fallback-model"],
        "temperature": 0, "max_tokens": 32, "timeout": 2,
    }}
    llm.supports_tools = {"ie_agent": True}
    llm.max_retries = 0
    llm.initial_backoff = 0

    result = llm.chat("ie_agent", [{"role": "user", "content": "cek"}])
    assert [call.kwargs["model"] for call in mock_client.chat.completions.create.call_args_list] == [
        "primary-model", "fallback-model"
    ]
    assert result["model_used"] == "fallback-model"
    assert result["fallback_used"] is True


@pytest.mark.mock
def test_llm_reports_generic_error_when_all_models_fail():
    from openai import InternalServerError
    from app.llm_client import LLMClientError

    llm = LLMClient.__new__(LLMClient)
    llm.client = MagicMock()
    llm.roles_config = {"ie_agent": {"enabled": True, "model": "primary", "fallback_models": ["fallback"]}}
    llm.supports_tools = {"ie_agent": True}
    llm.max_retries = 0
    llm.initial_backoff = 0
    llm.client.chat.completions.create.side_effect = InternalServerError(
        message="provider rate limited", response=MagicMock(status_code=503, headers={}), body=None
    )
    with pytest.raises(LLMClientError) as exc:
        llm.chat("ie_agent", [{"role": "user", "content": "hello"}])
    assert "api_key" not in str(exc.value).lower()


@pytest.mark.mock
def test_solver_state_and_error_events_are_defined():
    # Required event contract coverage. Current event manager exposes only four event emitters.
    from app.events import ConnectionManager
    manager = ConnectionManager()
    assert callable(getattr(manager, "emit_solver_state", None))
    assert callable(getattr(manager, "emit_error", None))
