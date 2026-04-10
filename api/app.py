"""FastAPI app exposing chat API and static frontend."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api.chat_service import process_user_message
from dashboard.charts import build_dashboard_payload
from observability.tracing import read_logs

project_root = Path(__file__).resolve().parent.parent
frontend_dir = project_root / "frontend"
plot_dir = project_root / "tool_plot_output"
plot_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="LangChain Chatbot Web API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")
app.mount("/tool_plot_output", StaticFiles(directory=plot_dir), name="tool_plot_output")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
    selected_chart_id: str | None = None
    selected_chart_context: dict[str, Any] | None = None
    model_name: str | None = None
    api_key: str | None = None


class ChatResponse(BaseModel):
    assistant_text: str
    session_id: str
    plot_url: str | None = None


class LogStreamResponse(BaseModel):
    items: list[dict[str, Any]]


class DashboardResponse(BaseModel):
    kpis: list[dict[str, Any]]
    charts: list[dict[str, Any]]


@app.get("/")
def serve_index() -> FileResponse:
    index_path = frontend_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or str(uuid4())
    result = process_user_message(
        session_id=session_id,
        user_input=request.message.strip(),
        selected_chart_id=request.selected_chart_id,
        selected_chart_context=request.selected_chart_context,
        model_name=request.model_name,
        api_key=request.api_key,
    )

    plot_path = result.get("plot_path")
    plot_url = None
    if isinstance(plot_path, str) and plot_path.startswith("tool_plot_output/"):
        plot_url = "/" + plot_path.replace("\\", "/")

    return ChatResponse(
        assistant_text=str(result.get("assistant_text", "")),
        session_id=session_id,
        plot_url=plot_url,
    )


@app.get("/api/logs/pipeline", response_model=LogStreamResponse)
def get_pipeline_logs(session_id: str | None = None, limit: int = 200) -> LogStreamResponse:
    return LogStreamResponse(items=read_logs("pipeline", session_id=session_id, limit=limit))


@app.get("/api/logs/traces", response_model=LogStreamResponse)
def get_model_traces(session_id: str | None = None, limit: int = 200) -> LogStreamResponse:
    return LogStreamResponse(items=read_logs("model", session_id=session_id, limit=limit))


@app.get("/api/dashboard", response_model=DashboardResponse)
def get_dashboard() -> DashboardResponse:
    payload = build_dashboard_payload()
    return DashboardResponse(kpis=payload["kpis"], charts=payload["charts"])
