import logging
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.backend_client import get_backend_client
from app.events import event_manager
from app.ie_agent import AgentResponse, IEAgent
from app.llm_client import check_llm_health
from app.memory import session_memory

app = FastAPI(title="Stock Memory Copilot Agent Service", version="0.1.0")
logger = logging.getLogger("agent_service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique user session ID")
    message: str = Field(..., description="User message text in Indonesian")


@app.post("/chat", response_model=AgentResponse)
async def chat_endpoint(req: ChatRequest):
    """Processes user chat, runs the IE agent loop, and streams real-time events over /ws."""
    agent = IEAgent()
    try:
        return await agent.run(session_id=req.session_id, user_message=req.message)
    except Exception as exc:
        logger.error("chat failed session=%s error_type=%s", req.session_id, type(exc).__name__)
        await event_manager.emit_error(req.session_id, "Permintaan gagal diproses.")
        raise HTTPException(status_code=500, detail="Permintaan gagal diproses.") from exc


@app.post("/proposals/{update_id}/confirm")
async def confirm_proposal(update_id: str):
    """
    Called by UI (not an LLM tool).
    Fetches latest base_product_revision from backend, confirms proposal,
    and broadcasts board_update.
    """
    backend = get_backend_client()
    try:
        prop_state = backend.get_update_state(update_id)
        product_id = prop_state.get("product_id")
        if not product_id:
            raise HTTPException(status_code=400, detail="Proposal does not contain valid product_id")

        prod_state = backend.get_product_state(product_id)
        current_rev = prod_state.get("revision", 1)

        result = backend.confirm_update(update_id=update_id, base_product_revision=current_rev)
        await event_manager.emit_board_update("global", {
            "action": "proposal_confirmed",
            "update_id": update_id,
            "product_id": product_id,
            "revision": current_rev,
        })
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/proposals/{update_id}/reject")
async def reject_proposal(update_id: str):
    """
    Called by UI (not an LLM tool).
    Rejects proposal and broadcasts board_update.
    """
    backend = get_backend_client()
    try:
        result = backend.reject_update(update_id=update_id)
        await event_manager.emit_board_update("global", {
            "action": "proposal_rejected",
            "update_id": update_id,
        })
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.websocket("/ws")
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str = "default"):
    """WebSocket endpoint for receiving real-time agent and board events."""
    await event_manager.connect(websocket)
    try:
        session = session_memory.get_or_create(session_id)
        await websocket.send_json({
            "type": "session_snapshot",
            "session_id": session_id,
            "parameters": {key: value.model_dump() for key, value in session.parameters.items()},
            "messages": session.get_recent_messages(50),
            "clarification_turns": session.clarification_turns,
        })
        while True:
            # Keep connection alive receiving any client message
            await websocket.receive_text()
    except WebSocketDisconnect:
        event_manager.disconnect(websocket)


@app.get("/health/llm")
def health_llm():
    """Reports direct OpenRouter connectivity and available models."""
    return check_llm_health()


@app.get("/health")
def health():
    return {"status": "ok"}
