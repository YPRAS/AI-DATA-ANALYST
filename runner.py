import sys
import pandas as pd
import matplotlib.pyplot as plt
import traceback
import json
import io
import os

# Load dataset
try:
    csv_path = os.getenv("CSV_PATH", "").strip()
    if not csv_path:
        raise ValueError("CSV_PATH env var is required but missing")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at path: {csv_path}")

    df = pd.read_csv(csv_path)
except Exception as e:
    print(json.dumps({
        "status": "error",
        "stdout": "",
        "error": f"CSV load error: {str(e)}",
        "plot_path": None
    }))
    sys.exit(1)

# Read code
code = sys.stdin.read()

# Capture stdout
stdout_buffer = io.StringIO()
sys_stdout_original = sys.stdout
sys.stdout = stdout_buffer

result = {
    "status": "success",
    "stdout": "",
    "error": None,
    "plot_path": None
}

def _matplotlib_has_chart():
    for fig_num in plt.get_fignums():
        fig = plt.figure(fig_num)
        for ax in fig.axes:
            if ax.has_data() or ax.images or ax.collections or ax.patches or ax.lines:
                return True
    return False

def _find_plotly_figure(local_scope):
    for value in local_scope.values():
        value_type = type(value)
        value_module = getattr(value_type, "__module__", "")
        if value_module.startswith("plotly"):
            return value
    return None

try:
    plt.clf()

    local_vars = {
        "df": df,
        "plt": plt
    }

    exec(code, {}, local_vars)

    plot_dir = "/tool_plot_output"
    os.makedirs(plot_dir, exist_ok=True)

    # Prefer matplotlib/seaborn output when chart content exists.
    if _matplotlib_has_chart():
        plot_path = os.path.join(plot_dir, "output.png")
        plt.savefig(plot_path)
        result["plot_path"] = plot_path
    else:
        # Fallback to plotly if user returned a plotly figure.
        plotly_fig = _find_plotly_figure(local_vars)
        if plotly_fig is not None:
            plot_path = os.path.join(plot_dir, "output.png")
            try:
                plotly_fig.write_image(plot_path)
                result["plot_path"] = plot_path
            except Exception:
                # Static export may fail when image backends are unavailable.
                html_path = os.path.join(plot_dir, "output.html")
                plotly_fig.write_html(html_path)
                result["plot_path"] = html_path

except Exception as e:
    result["status"] = "error"
    result["error"] = traceback.format_exc()

# Restore stdout
sys.stdout = sys_stdout_original
result["stdout"] = stdout_buffer.getvalue()

# Print JSON output
print(json.dumps(result))