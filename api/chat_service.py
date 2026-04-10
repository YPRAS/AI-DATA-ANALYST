"""Shared chat service for terminal and API usage."""
from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any
from uuid import uuid4

from graph.graph_builder import build_graph
from observability.tracing import (
    clear_trace_context,
    extract_message_trace,
    log_model_trace,
    log_pipeline,
    set_trace_context,
)

_graph = build_graph()
_session_lock = Lock()
_session_messages: dict[str, list[Any]] = {}


def _extract_message_content(message: Any) -> str:
    """Handle both dict messages and LangChain message objects."""
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")

    if isinstance(content, list):
        return " ".join(str(part) for part in content)
    return str(content)


def _collect_plot_path(value: Any) -> str | None:
    """Recursively discover latest tool plot path from nested message payloads."""
    if isinstance(value, dict):
        found = value.get("plot_path")
        if isinstance(found, str) and found.strip():
            return found
        for nested in value.values():
            nested_found = _collect_plot_path(nested)
            if nested_found:
                return nested_found
    elif isinstance(value, list):
        for nested in reversed(value):
            nested_found = _collect_plot_path(nested)
            if nested_found:
                return nested_found
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return _collect_plot_path(parsed)
    return None


def _extract_plot_path(messages: list[Any]) -> str | None:
    for message in reversed(messages):
        payload = message if isinstance(message, dict) else getattr(message, "__dict__", None)
        if payload is None:
            payload = {
                "content": getattr(message, "content", ""),
                "additional_kwargs": getattr(message, "additional_kwargs", {}),
            }
        plot_path = _collect_plot_path(payload)
        if plot_path:
            return plot_path
    return None


def process_user_message(
    session_id: str,
    user_input: str,
    selected_chart_id: str | None = None,
    selected_chart_context: dict[str, Any] | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
) -> dict[str, str | None]:
    """Append user message, invoke graph, and return assistant text + optional plot path."""
    trace_id = str(uuid4())
    set_trace_context(session_id=session_id, trace_id=trace_id)

    enriched_user_input = user_input
    if selected_chart_id and selected_chart_context:
        chart_context_text = json.dumps(selected_chart_context, ensure_ascii=True)
        enriched_user_input = (
            f"{user_input}\n\n"
            f"[Selected chart id: {selected_chart_id}]\n"
            f"[Selected chart context: {chart_context_text}]"
        )

    log_pipeline(
        "request",
        "start",
        details={
            "user_input_preview": user_input[:400],
            "selected_chart_id": selected_chart_id,
        },
    )
    log_model_trace(
        "user_message",
        details={
            "raw_user_input": user_input,
            "enriched_user_input": enriched_user_input,
            "selected_chart_id": selected_chart_id,
            "selected_chart_context": selected_chart_context,
        },
    )

    with _session_lock:
        messages = list(_session_messages.get(session_id, []))
        messages.append({"role": "user", "content": enriched_user_input})

    base_message_count = len(messages)
    invoke_started = time.perf_counter()

    try:
        log_pipeline(
            "graph.invoke",
            "start",
            details={"input_message_count": base_message_count},
        )
        result = _graph.invoke(
            {
                "messages": messages,
                "session_id": session_id,
                "trace_id": trace_id,
                "model_name": model_name,
                "api_key": api_key,
            }
        )
        invoke_elapsed_ms = round((time.perf_counter() - invoke_started) * 1000, 2)
        log_pipeline(
            "graph.invoke",
            "complete",
            details={"duration_ms": invoke_elapsed_ms},
        )

        updated_messages = result.get("messages", [])
        final_message = _extract_message_content(updated_messages[-1]) if updated_messages else ""
        plot_path = _extract_plot_path(updated_messages)

        new_messages = updated_messages[base_message_count:]
        for idx, message in enumerate(new_messages):
            log_model_trace(
                "message",
                details={
                    "index": idx,
                    "trace_message": extract_message_trace(message),
                },
            )

        with _session_lock:
            _session_messages[session_id] = list(updated_messages)

        log_pipeline(
            "request",
            "complete",
            details={
                "duration_ms": invoke_elapsed_ms,
                "assistant_preview": final_message[:400],
                "plot_path": plot_path,
            },
        )

        return {
            "assistant_text": final_message,
            "plot_path": plot_path,
            "session_id": session_id,
        }
    except Exception as exc:
        invoke_elapsed_ms = round((time.perf_counter() - invoke_started) * 1000, 2)
        log_pipeline(
            "graph.invoke",
            "error",
            details={"duration_ms": invoke_elapsed_ms, "error": str(exc)},
        )
        log_pipeline(
            "request",
            "error",
            details={"error": str(exc)},
        )
        raise
    finally:
        clear_trace_context()
