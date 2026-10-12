import os
from pydantic import BaseModel


class AgentConfig(BaseModel):
    backend_url: str = os.getenv("BACKEND_URL", "https://stock-copilot-backend.onrender.com")
    freshness_hours: float = float(os.getenv("FRESHNESS_HOURS", "12.0"))
    max_clarification_turns: int = int(os.getenv("MAX_CLARIFICATION_TURNS", "3"))
    max_messages_window_k: int = int(os.getenv("MAX_MESSAGES_WINDOW_K", "6"))
    max_tool_calls_per_turn: int = int(os.getenv("MAX_TOOL_CALLS_PER_TURN", "5"))
    retry_on_conflict: int = int(os.getenv("RETRY_ON_CONFLICT", "1"))


config = AgentConfig()
