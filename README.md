![Diagram 1](documents/dashboard.png)
![Diagram 2](documents/system_architecture.png)

# LangChain Chatbot - AI Data Analyst

A web-based AI data analyst that chats over a marketing dataset, executes Python analysis code safely in Docker, renders dashboard charts, and exposes observability logs for pipeline/model traces.


## Features

- Chat UI with model selection and optional API key override
- Dashboard with KPI cards + interactive Plotly charts
- Chart-aware chat context (select a chart, then ask chart-specific questions)
- Python tool execution in an isolated Docker container
- Plot output handling (PNG/HTML) and in-chat plot rendering
- Pipeline + model trace logging with live log tabs

## Architecture

- **Frontend** (`frontend/`): Chat panel, dashboard UI, chart rendering, log polling
- **API layer** (`api/app.py`): FastAPI endpoints for chat, dashboard, and logs
- **Chat service** (`api/chat_service.py`): Session state, graph invocation, trace logging
- **Graph + agent** (`graph/`, `agents/`): LangGraph state flow and LangChain agent setup
- **Tool execution** (`agents/tools.py`, `tools/execution_tool.py`, `runner.py`): Executes generated Python code against dataset inside Docker
- **Dashboard builder** (`dashboard/charts.py`): KPI and Plotly payload generation from CSV
- **Observability** (`observability/tracing.py`): Structured model traces + readable pipeline logs

Detailed request flow is documented in [`SEQUENCE_DIAGRAM.md`](./SEQUENCE_DIAGRAM.md).

https://mermaid.live/edit#pako:eNp9Vl1P4zoQ_StWnlpRmsJttzQPSFCg2itY0BZeVkjBTYbUF8f22k6XXsR_vzNO0pav24cmtufMx5k5Vl6iTOcQJZGD3xWoDM4ELywv7xXDH6-8VlW5AFuvDbdeZMJw5dkd447duc-OLs7p7MJq5UHlrPPw2LzG3Jj-P-6h-xFzcvM9gLjz9Np54EYEc7P-zHw6J-vpkns2B7sSGTSQDLdSV299gZ0R9JKrYma5WSKuoGcc_tNFJWQO9gvoCUFPCsBXDEdPF4fHF_aXl1dtnjOrf7MrJFt-NLslo5u1X2rFbrWW6Nzjw8XwDFnlhVYprb8IchG4uJHas-vKm8o38NTgVqrDVvwZ8Po0IK8XxBdfCCn8GrF6dx17yzOhii9in52ShzPulgvNLfU6b9-pFda7BlhDf2gPTK_A4owk7LsSXnCJDgtgeyznnjOpeV7bXpzvHx_jLCRsdn7L4noT1_u4TWihcnjuL30pW-_vEDQOm2y28OPjs9OEhT6nm-PU8DWF7jQ1np3ut76ejHCYXV3Nhyw2Htjf8-sf_5OJ1IWLjTAghQLGURfbbeIYHOsYLfG06O4mi01KmAWep2Ta6ff7zTEebHJ8FNKDhZyRzYccafNNets23PXIIOjI0g3gfG1x10Dn1aIUnpXgHDWps8e0oXnErjmQkHmMGZhhGUn82XffE3BzPW8YIGnuVjbFwozVWLlLKxy5tImyU-N03jLgwKeBprQJhC3ButKW0dh5zGIHNUtYUHRfqJV-gg6ee9gM4ozSa6cgKLhTkjZTxUvoMUw3fYJ1F4M08CY31_YG8SjuJCg841KyP8IvmVs7DyVVVRrKMKi4jcmlr9Ud7BVADs1Y0g8doc9bpCTcA2ktfW07dEF3t3a3tVWusyfsn61UCyC7DSpZHbyFXCCHc76Cplu6uSiMKmKS0JsAbW2UPY6FqzBx5C9HUAzWahuHm8Vwv2xweLe3VVIdNbncOYGsKx8HRy2DLYF1jyqDsschCu1pe9MMRx16p6e0ia3HMfBb72k7DejAebZJ7f0Ehf6yRmp77bjj3JZGQht7utXU2wC9reMeDiOeIeUi_6A1ktJPcEYrh3L51Edl5a6L7ptLI4jOo95LVkMscouNJiQTJRKI2MoYjU0EJblFVWJlXEa9qLAijxJvK-hFJdiS0zJ6Ie_3kV9CCfdRgq85PHIiNrpXrwjDi_yX1mWLtLoqllHyyKXDVd2f5qtgYxJymupK-Sj562gcfETJS_QcJd9G_cFkOBwMjw6G4_HwWy9aR8nhuD8Zjiajg-Hh4WAyGkwOX3vRvyHooD8ZDMbjo8FweDQaj0ejYS-CXOAMX9VfJuED5fU_ArjRkg


1. Frontend sends `POST /api/chat` with user message and optional selected chart context.
2. API calls `process_user_message(...)`.
3. Chat service invokes LangGraph, which invokes the agent + LLM.
4. If needed, LLM calls the `python` tool.
5. Tool executes code in Docker (`python_code_executor:v1`) and may write plot output to `tool_plot_output/`.
6. Response returns as `assistant_text` + optional `plot_url`.
7. Frontend renders answer, plot, dashboard updates, and logs.

## Project Structure

```text
langchain_chatbot/
|-- api/
|   |-- app.py                   # FastAPI app and routes
|   `-- chat_service.py          # Session handling + graph invocation
|-- agents/
|   |-- agent.py                 # Agent + model selection
|   |-- prompts.py               # System prompt
|   `-- tools.py                 # Tool wrapper exposed to agent
|-- dashboard/
|   |-- __init__.py
|   `-- charts.py                # KPI + Plotly dashboard payloads
|-- frontend/
|   |-- index.html               # Main UI shell
|   |-- styles.css               # UI styling
|   `-- app.js                   # Chat, dashboard, logs, modal interactions
|-- graph/
|   `-- graph_builder.py         # LangGraph state graph
|-- logs/
|   |-- pipeline.log             # Human-readable pipeline log lines
|   `-- model_traces.jsonl       # Structured model/tool traces
|-- observability/
|   |-- __init__.py
|   `-- tracing.py               # Logging, trace context, log readers
|-- raw_data/
|   `-- cleaned_data.csv         # Dataset used by dashboard + tool
|-- tools/
|   `-- execution_tool.py        # Docker execution bridge
|-- tool_plot_output/            # Generated plots served as static files
|-- Dockerfile                   # Executor image (runner.py)
|-- main.py                      # Terminal chat entry point
|-- runner.py                    # In-container code executor runtime
|-- requirements.txt             # Python dependencies
|-- SEQUENCE_DIAGRAM.md          # End-to-end sequence flow (Mermaid)
`-- .env                         # Local environment variables (not for commit)
```

## API Endpoints

- `GET /` -> serves frontend
- `POST /api/chat` -> returns `assistant_text`, `session_id`, optional `plot_url`
- `GET /api/dashboard` -> dashboard KPI + chart payload
- `GET /api/logs/pipeline` -> session-filtered pipeline logs
- `GET /api/logs/traces` -> session-filtered model traces
- `GET /frontend/*` and `GET /tool_plot_output/*` -> static files

## Local Setup

### 1) Create and activate virtual environment

```bash
python -m venv .venv
.venv\Scripts\Activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

If you hit missing package errors for LLM stack modules, install:

```bash
pip install langchain langgraph langchain-groq python-dotenv
```

### 3) Configure environment

Create/update `.env` with your provider key:

```env
GROQ_API_KEY=your_key_here
```

### 4) Build Docker executor image (required for Python tool calls)

From project root:

```bash
docker build -t python_code_executor:v1 .
```

### 5) Run the web app

```bash
uvicorn api.app:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## Usage Notes

- Select a dashboard chart to attach chart context to chat.
- Ask analysis questions; the model can call the Python tool when needed.
- Pipeline and model trace tabs update automatically.
- Chat plot images in assistant responses support click-to-enlarge modal view.

