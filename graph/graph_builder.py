"""Graph construction for LangGraph/LangChain workflows."""
import hashlib
import time

from typing import Any, List, TypedDict
from langgraph.graph import StateGraph
from agents.agent import build_agent
from agents.prompts import SYSTEM_PROMPT
from observability.tracing import log_model_trace, log_pipeline


class AgentState(TypedDict):
    messages: List[Any]
    session_id: str
    trace_id: str
    model_name: str | None
    api_key: str | None


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def agent_node(state: AgentState):  
    session_id = state.get("session_id")
    trace_id = state.get("trace_id")
    started = time.perf_counter()
    log_pipeline(
        "graph.agent_node",
        "start",
        session_id=session_id,
        trace_id=trace_id,
        details={"input_message_count": len(state["messages"])},
    )
    try:
        agent = build_agent(
            model_name=state.get("model_name"),
            api_key=state.get("api_key"),
        )
        log_model_trace(
            "llm_request_context",
            session_id=session_id,
            trace_id=trace_id,
            details={
                "model_name": state.get("model_name"),
                "system_prompt": SYSTEM_PROMPT,
                "system_prompt_hash": _hash_text(SYSTEM_PROMPT),
                "input_message_count": len(state["messages"]),
            },
        )
        response = agent.invoke({
            "messages": state["messages"]
        })
        returned_messages = response["messages"]
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        log_pipeline(
            "graph.agent_node",
            "complete",
            session_id=session_id,
            trace_id=trace_id,
            details={
                "duration_ms": elapsed_ms,
                "output_message_count": len(returned_messages),
            },
        )
        return {
            "messages": returned_messages,
            "session_id": state.get("session_id", ""),
            "trace_id": state.get("trace_id", ""),
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        log_pipeline(
            "graph.agent_node",
            "error",
            session_id=session_id,
            trace_id=trace_id,
            details={"duration_ms": elapsed_ms, "error": str(exc)},
        )
        raise


def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)

    workflow.set_entry_point("agent")
    workflow.set_finish_point("agent")

    return workflow.compile()