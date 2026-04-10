"""Simple local tracing and log readers."""
from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

_session_id_var: ContextVar[str | None] = ContextVar("trace_session_id", default=None)
_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

_log_lock = Lock()
_project_root = Path(__file__).resolve().parent.parent
_log_dir = _project_root / "logs"
_pipeline_log_path = _log_dir / "pipeline.log"
_model_trace_path = _log_dir / "model_traces.jsonl"


def set_trace_context(session_id: str, trace_id: str) -> None:
    _session_id_var.set(session_id)
    _trace_id_var.set(trace_id)


def clear_trace_context() -> None:
    _session_id_var.set(None)
    _trace_id_var.set(None)


def get_trace_context() -> tuple[str | None, str | None]:
    return _session_id_var.get(), _trace_id_var.get()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    _log_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=True)
    with _log_lock:
        with path.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")


def _append_text_line(path: Path, line: str) -> None:
    _log_dir.mkdir(parents=True, exist_ok=True)
    with _log_lock:
        with path.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")


def _preview(value: Any, max_len: int = 400) -> str:
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def log_pipeline(
    step: str,
    status: str,
    *,
    session_id: str | None = None,
    trace_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    current_session_id, current_trace_id = get_trace_context()
    timestamp = utc_now_iso()
    final_session_id = session_id or current_session_id or "unknown-session"
    final_trace_id = trace_id or current_trace_id or "unknown-trace"
    detail_pairs: list[str] = []
    for key, value in (details or {}).items():
        detail_pairs.append(f"{key}={_preview(value, 200)}")
    detail_text = " ".join(detail_pairs)
    line = (
        f"[{timestamp}] [session={final_session_id}] [trace={final_trace_id}] "
        f"[step={step}] [status={status}] {detail_text}".rstrip()
    )
    _append_text_line(_pipeline_log_path, line)


def log_model_trace(
    event: str,
    *,
    session_id: str | None = None,
    trace_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    current_session_id, current_trace_id = get_trace_context()
    payload = {
        "timestamp": utc_now_iso(),
        "session_id": session_id or current_session_id,
        "trace_id": trace_id or current_trace_id,
        "event": event,
        "details": details or {},
    }
    _append_jsonl(_model_trace_path, payload)


def read_logs(kind: str, session_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    path = _pipeline_log_path if kind == "pipeline" else _model_trace_path
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    if kind == "pipeline":
        rows_text: list[dict[str, Any]] = []
        session_filter = f"[session={session_id}]" if session_id else None
        for line in reversed(lines):
            if not line.strip():
                continue
            if session_filter and session_filter not in line:
                continue
            rows_text.append({"line": line})
            if len(rows_text) >= max(1, limit):
                break
        rows_text.reverse()
        return rows_text

    rows: list[dict[str, Any]] = []

    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue

        if session_id and parsed.get("session_id") != session_id:
            continue

        rows.append(parsed)
        if len(rows) >= max(1, limit):
            break

    rows.reverse()
    return rows


def extract_message_trace(message: Any) -> dict[str, Any]:
    role = "assistant"
    message_type = type(message).__name__
    if isinstance(message, dict):
        role = str(message.get("role", role))
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")
        additional_kwargs = message.get("additional_kwargs", {})
        usage_metadata = message.get("usage_metadata", {})
        response_metadata = message.get("response_metadata", {})
        name = message.get("name")
    else:
        role = getattr(message, "role", role)
        content = getattr(message, "content", "")
        tool_calls = getattr(message, "tool_calls", None)
        additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
        usage_metadata = getattr(message, "usage_metadata", {}) or {}
        response_metadata = getattr(message, "response_metadata", {}) or {}
        name = getattr(message, "name", None)

    if isinstance(content, list):
        content = " ".join(str(part) for part in content)

    token_usage = {}
    if isinstance(response_metadata, dict):
        candidate = response_metadata.get("token_usage", {})
        if isinstance(candidate, dict):
            token_usage = candidate

    reasoning_tokens = None
    completion_details = token_usage.get("completion_tokens_details", {})
    if isinstance(completion_details, dict):
        reasoning_tokens = completion_details.get("reasoning_tokens")

    return {
        "message_type": message_type,
        "role": role,
        "name": name,
        "content_preview": _preview(content),
        "tool_calls": tool_calls,
        "additional_kwargs": additional_kwargs,
        "usage_metadata": usage_metadata,
        "response_metadata": response_metadata,
        "token_usage": token_usage,
        "reasoning_tokens": reasoning_tokens,
    }
