import asyncio
import datetime
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.backend_client import BackendAPIError, BackendClient, get_backend_client
from app.config import config
from app.events import event_manager
from app.llm_client import chat
from app.memory import SessionState, session_memory
from app.tools import TOOL_DEFINITIONS, ToolExecutor

logger = logging.getLogger("ie_agent")


class AgentResponse(BaseModel):
    intent: str = Field(..., description="Detected user intent, e.g. inquiry, update_stock, calculate_gap")
    extracted: Dict[str, Any] = Field(default_factory=dict, description="Extracted parameters")
    conflicts: List[str] = Field(default_factory=list, description="Detected conflicts with backend state")
    next_action: str = Field(..., description="Action to take, e.g. clarify, propose_update, run_solver, answer")
    message_to_user: str = Field(..., description="Polite and direct Indonesian response to the user")


SAFE_FALLBACK_MESSAGE = (
    "Maaf, terjadi kendala saat memproses permintaan secara terstruktur. "
    "Bisa tolong ulangi atau jelaskan kembali data stok yang ingin diperiksa?"
)


def _safe_error_detail(exc: Exception, limit: int = 240) -> str:
    """Return bounded diagnostics without exposing API credentials."""
    detail = str(exc).replace("\r", " ").replace("\n", " ").strip()
    detail = re.sub(r"(?i)(bearer\s+|api[_-]?key\s*[=:]\s*)\S+", r"\1[redacted]", detail)
    detail = re.sub(r"(?i)sk-[A-Za-z0-9_-]+", "[redacted]", detail)
    if len(detail) > limit:
        return f"{detail[:limit - 3]}..."
    return detail or "Tidak ada detail dari provider."


def detect_state_conflicts(
    prod_state: Dict[str, Any],
    claimed_stock: Optional[int] = None,
    required_by_str: Optional[str] = None,
    freshness_hours: float = 12.0,
) -> List[str]:
    """Detect discrepancies between user statements and backend data."""
    conflicts = []
    facts = prod_state.get("facts", {})
    on_hand = facts.get("on_hand_qty")

    # 1. Stock claim discrepancy
    if claimed_stock is not None and on_hand is not None and claimed_stock != on_hand:
        conflicts.append(
            f"Konflik stok: Anda menyebutkan stok {claimed_stock}, namun database mencatat {on_hand} {prod_state.get('unit', '')}."
        )

    # 2. Stale stock_as_of check
    stock_as_of_str = facts.get("stock_as_of")
    if stock_as_of_str:
        try:
            stock_dt = datetime.datetime.fromisoformat(stock_as_of_str)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            hours_diff = (now_dt - stock_dt).total_seconds() / 3600.0
            if hours_diff > freshness_hours:
                conflicts.append(
                    f"Data stok fisik tercatat sejak {stock_as_of_str} (lebih dari {freshness_hours} jam lalu). Diperlukan verifikasi stok terkini."
                )
        except Exception:
            pass

    # 3. Incoming orders ETA checks
    incoming_orders = facts.get("incoming_orders", []) or []
    req_by_dt = None
    if required_by_str:
        try:
            req_by_dt = datetime.datetime.fromisoformat(required_by_str)
        except Exception:
            pass

    for order in incoming_orders:
        order_id = order.get("order_id", "PO")
        if not order.get("eta_verified_at"):
            conflicts.append(f"Pesanan masuk {order_id} belum memiliki ETA yang terverifikasi.")

        arr_str = order.get("expected_arrival_at")
        if arr_str and req_by_dt:
            try:
                arr_dt = datetime.datetime.fromisoformat(arr_str)
                if arr_dt > req_by_dt:
                    conflicts.append(
                        f"Pesanan {order_id} diperkirakan tiba ({arr_str}) setelah batas waktu kebutuhan ({required_by_str})."
                    )
            except Exception:
                pass

    return conflicts


class IEAgent:
    """Inventory Engineer Agent (Database Administrator for Stock Data)."""

    def __init__(
        self,
        backend_client: Optional[BackendClient] = None,
        max_tool_calls: Optional[int] = None,
        max_clarification_turns: Optional[int] = None,
        freshness_hours: Optional[float] = None,
    ):
        self.backend = backend_client or get_backend_client()
        self.tool_executor = ToolExecutor(backend_client=self.backend)
        self.max_tool_calls = max_tool_calls or config.max_tool_calls_per_turn
        self.max_clarification_turns = max_clarification_turns or config.max_clarification_turns
        self.freshness_hours = freshness_hours or config.freshness_hours

    def _build_system_prompt(self, session: SessionState) -> str:
        param_table = session.format_parameter_table()
        return f"""Anda adalah IE Agent (Inventory Engineer / Database Administrator untuk data stok).
Tugas Anda:
1. Memahami pesan pengguna dalam bahasa Indonesia.
2. Mengekstrak parameter inventaris: product_id, on_hand_qty, target_qty, expected_outgoing_qty, required_by.
3. Memeriksa konsistensi data dengan memanggil tool get_product_state bila product_id diketahui.
4. Mendeteksi konflik antara pernyataan user dan data sistem (stok berbeda, data kadaluarsa, ETA belum verifikasi).
5. Bertanya HANYA SATU pertanyaan klarifikasi pada satu waktu jika ada parameter penting yang kurang atau ada konflik.
6. Mengusulkan perubahan data dengan tool propose_update HANYA jika pengguna menyatakan fakta baru yang sudah jelas.
7. Memanggil tool run_solver HANYA SETELAH task di-validate (status READY) dan TIDAK ADA konflik.
8. ATURAN MUTLAK: JANGAN PERNAH menghitung atau menyebut angka hasil perhitungan (projected_balance, shortfall) dari pikiran sendiri. SEMUA angka hasil WAJIB berasal dari hasil kembalian tool run_solver.

Tabel Parameter Sesi Terkini:
{param_table}

Keluaran non-tool WAJIB berupa JSON valid dengan format:
{{
  "intent": "<inquiry / update_stock / calculate_gap / clarify>",
  "extracted": {{"product_id": null, "on_hand_qty": null, "target_qty": null, "expected_outgoing_qty": null, "required_by": null}},
  "conflicts": ["<daftar pesan konflik jika ada>"],
  "next_action": "<clarify / propose_update / run_solver / answer>",
  "message_to_user": "<Pesan bahasa Indonesia yang jelas, sopan, dan langsung ke poin>"
}}
"""

    async def run(self, session_id: str, user_message: str) -> AgentResponse:
        session = session_memory.get_or_create(session_id)
        msg_id = f"MSG-{uuid.uuid4().hex[:6]}"
        session.add_message("user", user_message)

        await event_manager.emit_agent_state("thinking", session_id)
        await event_manager.emit_board_update(session_id, {
            "parameters": session.parameters,
            "clarification_turns": session.clarification_turns,
        })

        system_prompt = self._build_system_prompt(session)
        if session.clarification_turns >= self.max_clarification_turns:
            system_prompt += (
                "\n\nBatas klarifikasi tercapai, tetapi sesi tetap aktif. "
                "Jangan mengulang pertanyaan yang sama. Ringkas data yang sudah ada "
                "dan minta hanya satu tindakan atau informasi paling penting berikutnya."
            )
        conversation: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        # Append recent K messages
        for m in session.get_recent_messages(config.max_messages_window_k):
            conversation.append(m)

        tool_calls_count = 0
        final_response_obj: Optional[AgentResponse] = None
        solver_result: Optional[Dict[str, Any]] = None

        while tool_calls_count < self.max_tool_calls:
            try:
                res = await asyncio.to_thread(chat, "ie_agent", conversation, TOOL_DEFINITIONS)
            except Exception as exc:
                error_type = type(exc).__name__
                error_detail = _safe_error_detail(exc)
                logger.error(
                    "LLM call failed session=%s error_type=%s detail=%s",
                    session_id,
                    error_type,
                    error_detail,
                )
                await event_manager.emit_error(
                    session_id,
                    f"Agent gagal menghubungi layanan AI ({error_type}): {error_detail}",
                    {"error_type": error_type, "detail": error_detail},
                )
                final_response_obj = AgentResponse(
                    intent="clarify",
                    extracted={},
                    conflicts=[],
                    next_action="clarify",
                    message_to_user="Agent sedang sibuk. Silakan coba lagi sebentar lagi.",
                )
                break
            raw_tool_calls = res.get("tool_calls")
            text_content = res.get("content", "")

            if raw_tool_calls:
                tool_calls_count += len(raw_tool_calls)
                await event_manager.emit_agent_state("calling_tool", session_id, {"tools": [t.function.name for t in raw_tool_calls]})

                # Append assistant tool call request message
                conversation.append({
                    "role": "assistant",
                    "content": text_content,
                    "tool_calls": raw_tool_calls,
                })

                for tc in raw_tool_calls:
                    fn_name = tc.function.name
                    fn_args_raw = tc.function.arguments
                    try:
                        fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                    except Exception:
                        fn_args = {}

                    # Ensure source_ref is injected for propose_update if missing
                    if fn_name == "propose_update" and not fn_args.get("source_ref"):
                        fn_args["source_ref"] = msg_id

                    tool_output = None
                    try:
                        if fn_name == "run_solver":
                            await event_manager.emit_solver_state("working", session_id, {"task_id": fn_args.get("task_id")})
                        tool_output = await asyncio.to_thread(self.tool_executor.dispatch, fn_name, fn_args)
                        if fn_name == "run_solver" and isinstance(tool_output, dict) and "projected_balance" in tool_output:
                            solver_result = tool_output
                            await event_manager.emit_solver_state("done", session_id, tool_output)
                    except BackendAPIError as e:
                        # Error handling: if 409 revision conflict, re-read and retry once
                        if e.status_code == 409 and fn_args.get("product_id"):
                            logger.warning("Revision mismatch (409) in tool %s. Re-reading product state...", fn_name)
                            try:
                                prod_state = await asyncio.to_thread(self.backend.get_product_state, fn_args["product_id"])
                                if "base_product_revision" in fn_args:
                                    fn_args["base_product_revision"] = prod_state.get("revision", 1)
                                tool_output = await asyncio.to_thread(self.tool_executor.dispatch, fn_name, fn_args)
                            except Exception as retry_err:
                                tool_output = {"error": f"Retry failed: {retry_err}"}
                        else:
                            tool_output = {"error": str(e)}
                    except Exception as e:
                        tool_output = {"error": str(e)}

                    if isinstance(tool_output, dict) and tool_output.get("error"):
                        if fn_name == "run_solver":
                            await event_manager.emit_solver_state("idle", session_id, {"task_id": fn_args.get("task_id")})
                        await event_manager.emit_error(session_id, f"Tool {fn_name} gagal diproses.", {"tool": fn_name})

                    if fn_name == "propose_update" and isinstance(tool_output, dict) and tool_output.get("update_id"):
                        await event_manager.emit_proposal_created(session_id, tool_output)

                    # Append tool result to conversation
                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_output),
                    })

                # Refresh board update after tools
                await event_manager.emit_board_update(session_id, {
                    "parameters": session.parameters,
                    "tool_executions": tool_calls_count,
                })
                continue

            # Assistant gave non-tool textual response
            parsed = self._parse_structured_output(text_content)
            if not parsed:
                # Retry once requesting valid JSON
                conversation.append({"role": "assistant", "content": text_content})
                conversation.append({
                    "role": "user",
                    "content": "Keluaran Anda harus berupa JSON valid sesuai schema AgentResponse. Tolong ulangi hanya dalam JSON.",
                })
                try:
                    retry_res = await asyncio.to_thread(chat, "ie_agent", conversation, None)
                    retry_text = retry_res.get("content", "")
                    parsed = self._parse_structured_output(retry_text)
                except Exception as exc:
                    error_type = type(exc).__name__
                    error_detail = _safe_error_detail(exc)
                    logger.error(
                        "LLM format retry failed session=%s error_type=%s detail=%s",
                        session_id,
                        error_type,
                        error_detail,
                    )
                    await event_manager.emit_error(
                        session_id,
                        f"Agent gagal memformat jawaban dari layanan AI ({error_type}): {error_detail}",
                        {"error_type": error_type, "detail": error_detail},
                    )
                    parsed = None

            if not parsed:
                # Safe fallback
                parsed = AgentResponse(
                    intent="clarify",
                    extracted={},
                    conflicts=[],
                    next_action="clarify",
                    message_to_user=SAFE_FALLBACK_MESSAGE,
                )

            final_response_obj = parsed
            break

        if not final_response_obj:
            final_response_obj = AgentResponse(
                intent="general",
                extracted={},
                conflicts=[],
                next_action="clarify",
                message_to_user=SAFE_FALLBACK_MESSAGE,
            )

        # Solver output is the only source of result numbers; never let the LLM invent them.
        if solver_result is not None:
            pb = solver_result.get("projected_balance")
            sf = solver_result.get("shortfall")
            final_response_obj = final_response_obj.model_copy(
                update={
                    "intent": "calculate_gap",
                    "next_action": "answer",
                    "message_to_user": f"Hasil perhitungan resmi: saldo proyeksi {pb} dan kekurangan stok (shortfall) {sf} unit.",
                }
            )

        # Update session memory from extracted
        self._sync_memory_from_extracted(session, final_response_obj.extracted)

        # If next action is clarify, increment clarification counter
        if final_response_obj.next_action == "clarify":
            session.clarification_turns = min(
                session.clarification_turns + 1,
                self.max_clarification_turns,
            )

        session.add_message("assistant", final_response_obj.message_to_user)
        await event_manager.emit_chat_message(session_id, "assistant", final_response_obj.message_to_user)
        await event_manager.emit_agent_state("done", session_id)

        return final_response_obj

    def _clarification_summary(self, session: SessionState) -> str:
        verified = [
            f"{name} = {entry.value} ({entry.source})"
            for name, entry in session.parameters.items()
            if entry.status == "VERIFIED" and entry.value is not None
        ]
        if verified:
            detail = "; ".join(verified)
        else:
            detail = "belum ada parameter yang terkonfirmasi"
        return (
            f"Batas klarifikasi tercapai. Ringkasan yang sudah terkumpul: {detail}. "
            "Silakan mulai ulang sesi dengan data lengkap untuk melanjutkan."
        )

    def _parse_structured_output(self, text: str) -> Optional[AgentResponse]:
        """Parses and validates LLM output against AgentResponse Pydantic model."""
        if not text:
            return None
        cleaned = text.strip()
        # Strip markdown fences if present
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            return AgentResponse(**data)
        except Exception:
            return None

    def _sync_memory_from_extracted(self, session: SessionState, extracted: Dict[str, Any]) -> None:
        for k, v in extracted.items():
            if v is not None:
                session.update_parameter(k, v, status="VERIFIED", source="user_claim")
