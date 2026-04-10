"""Tool wiring for chatbot agents."""
import time

from langchain.tools import tool
from tools.execution_tool import execute_python
from observability.tracing import log_model_trace, log_pipeline


@tool("python")
def python_executor(code: str) -> dict:
    """
    Executes Python code on the dataset.

    Tool input must be one JSON object:
    {"code": "<python code string>"}

    IMPORTANT:
    - DataFrame is already loaded as `df`
    - Always return print outputs
    - For charts, use matplotlib, seaborn, plotly

    Example:
    print(df.head())
    """
    code_preview = code[:400]
    started = time.perf_counter()
    log_pipeline(
        "tool.python_executor",
        "start",
        details={"code_preview": code_preview},
    )
    try:
        result = execute_python(code)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        log_pipeline(
            "tool.python_executor",
            "complete",
            details={
                "duration_ms": elapsed_ms,
                "tool_status": result.get("status"),
                "error": result.get("error"),
                "plot_path": result.get("plot_path"),
            },
        )
        log_model_trace(
            "tool_call",
            details={
                "tool_name": "python",
                "input_preview": code_preview,
                "output": {
                    "status": result.get("status"),
                    "stdout_preview": str(result.get("stdout", ""))[:400],
                    "error": result.get("error"),
                    "plot_path": result.get("plot_path"),
                },
                "duration_ms": elapsed_ms,
            },
        )
        return result
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        log_pipeline(
            "tool.python_executor",
            "error",
            details={"duration_ms": elapsed_ms, "error": str(exc)},
        )
        raise