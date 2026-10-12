from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParameterEntry(BaseModel):
    value: Any = None
    status: str = "MISSING"  # MISSING, UNVERIFIED, CONFLICT, VERIFIED
    source: str = "none"     # user_claim, backend_facts, backend_policy, etc.


class SessionState(BaseModel):
    session_id: str
    parameters: Dict[str, ParameterEntry] = Field(
        default_factory=lambda: {
            "product_id": ParameterEntry(),
            "on_hand_qty": ParameterEntry(),
            "target_qty": ParameterEntry(),
            "expected_outgoing_qty": ParameterEntry(),
            "required_by": ParameterEntry(),
        }
    )
    messages: List[Dict[str, str]] = Field(default_factory=list)
    clarification_turns: int = 0
    active_task_id: Optional[str] = None
    last_conflicts: List[str] = Field(default_factory=list)

    def update_parameter(self, name: str, value: Any, status: str, source: str) -> None:
        if name not in self.parameters:
            self.parameters[name] = ParameterEntry()
        self.parameters[name].value = value
        self.parameters[name].status = status
        self.parameters[name].source = source

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def get_recent_messages(self, k: int) -> List[Dict[str, str]]:
        return self.messages[-k:] if len(self.messages) > k else list(self.messages)

    def format_parameter_table(self) -> str:
        lines = [
            "| Parameter | Value | Status | Source |",
            "|---|---|---|---|",
        ]
        for name, entry in self.parameters.items():
            val_str = str(entry.value) if entry.value is not None else "-"
            lines.append(f"| {name} | {val_str} | {entry.status} | {entry.source} |")
        return "\n".join(lines)


class MemoryStore:
    """In-memory session manager."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}

    def get_or_create(self, session_id: str) -> SessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]

    def reset_session(self, session_id: str) -> SessionState:
        self._sessions[session_id] = SessionState(session_id=session_id)
        return self._sessions[session_id]


session_memory = MemoryStore()
