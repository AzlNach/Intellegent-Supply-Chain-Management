import json
import logging
from typing import Any, Dict, List
from starlette.websockets import WebSocket

logger = logging.getLogger("events")


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts real-time agent events."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected. Total clients: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info("WebSocket disconnected. Total clients: %d", len(self.active_connections))

    async def broadcast(self, event: Dict[str, Any]):
        """Broadcast event to all connected clients."""
        def _json_default(obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "dict"):
                return obj.dict()
            return str(obj)

        msg = json.dumps(event, default=_json_default)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(msg)
            except Exception as e:
                logger.warning("Failed to send WebSocket message: %s", e)
                disconnected.append(connection)

        for dead_conn in disconnected:
            self.disconnect(dead_conn)

    async def emit_agent_state(self, state: str, session_id: str, data: Any = None):
        await self.broadcast({
            "type": "agent_state",
            "state": state,
            "session_id": session_id,
            "data": data or {},
        })

    async def emit_board_update(self, session_id: str, board_data: Dict[str, Any]):
        await self.broadcast({
            "type": "board_update",
            "session_id": session_id,
            "board": board_data,
        })

    async def emit_chat_message(self, session_id: str, role: str, content: str):
        await self.broadcast({
            "type": "chat_message",
            "session_id": session_id,
            "role": role,
            "content": content,
        })

    async def emit_proposal_created(self, session_id: str, proposal_data: Dict[str, Any]):
        await self.broadcast({
            "type": "proposal_created",
            "session_id": session_id,
            "proposal": proposal_data,
        })

    async def emit_solver_state(self, state: str, session_id: str, data: Any = None):
        await self.broadcast({
            "type": "solver_state",
            "state": state,
            "session_id": session_id,
            "data": data or {},
        })

    async def emit_error(self, session_id: str, message: str, data: Any = None):
        await self.broadcast({
            "type": "error",
            "session_id": session_id,
            "message": message,
            "data": data or {},
        })


event_manager = ConnectionManager()
