"""Docker execution tool module."""
import subprocess
import json
from pathlib import Path

def execute_python(code: str) -> dict:
    try:
        project_root = Path(__file__).resolve().parent.parent
        data_path = project_root / "raw_data"
        csv_file_name = "cleaned_data.csv"
        host_csv_path = data_path / csv_file_name
        container_csv_path = f"/data/{csv_file_name}"
        plot_output_path = project_root / "tool_plot_output"
        plot_output_path.mkdir(parents=True, exist_ok=True)

        if not data_path.exists():
            return {
                "status": "error",
                "stdout": "",
                "error": f"Data directory not found: {data_path}",
                "plot_path": None
            }
        if not host_csv_path.exists():
            return {
                "status": "error",
                "stdout": "",
                "error": f"CSV file not found: {host_csv_path}",
                "plot_path": None
            }

        result = subprocess.run(
            [
                "docker", "run",
                "-i",
                "-e", f"CSV_PATH={container_csv_path}",
                "-v", f"{data_path}:/data:ro",
                "-v", f"{plot_output_path}:/tool_plot_output",
                "python_code_executor:v1"
            ],
            input=code,
            text=True,
            capture_output=True,
            timeout=20
        )

        if result.returncode != 0:
            return {
                "status": "error",
                "stdout": result.stdout or "",
                "error": result.stderr or "Docker execution failed",
                "plot_path": None
            }

        if not result.stdout.strip():
            return {
                "status": "error",
                "stdout": "",
                "error": "Executor returned empty output",
                "plot_path": None
            }

        parsed = json.loads(result.stdout)
        plot_path = parsed.get("plot_path")
        if isinstance(plot_path, str) and plot_path.startswith("/tool_plot_output/"):
            parsed["plot_path"] = plot_path.replace("/tool_plot_output/", "tool_plot_output/", 1)

        return parsed

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "stdout": "",
            "error": "Execution timed out",
            "plot_path": None
        }

    except Exception as e:
        return {
            "status": "error",
            "stdout": "",
            "error": str(e),
            "plot_path": None
        }