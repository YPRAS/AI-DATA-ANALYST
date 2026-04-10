const chatPanel = document.getElementById("chat-panel");
const chatForm = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const stopButton = document.getElementById("stop-button");
const modelSelect = document.getElementById("model-select");
const apiKeyInput = document.getElementById("api-key-input");
const dashboardTab = document.getElementById("tab-dashboard");
const pipelineTab = document.getElementById("tab-pipeline");
const tracesTab = document.getElementById("tab-traces");
const dashboardPanel = document.getElementById("panel-dashboard");
const pipelinePanel = document.getElementById("panel-pipeline");
const tracesPanel = document.getElementById("panel-traces");
const pipelineLogView = document.getElementById("pipeline-log-view");
const traceLogView = document.getElementById("trace-log-view");
const kpiGrid = document.getElementById("kpi-grid");
const dashboardChartGrid = document.getElementById("dashboard-chart-grid");
const selectedChartChatPill = document.getElementById("selected-chart-chat-pill");
const chatPlotModal = document.getElementById("chat-plot-modal");
const chatPlotModalImage = document.getElementById("chat-plot-modal-image");
const chatPlotModalClose = document.getElementById("chat-plot-modal-close");
const chatPlotModalBackdrop = document.getElementById("chat-plot-modal-backdrop");

let lastPipelineText = "";
let lastTraceSignature = "";
let selectedChartId = null;
let dashboardCharts = [];
let dashboardSignature = "";
let isGenerating = false;
let activeRequestController = null;
let activeRenderToken = 0;
let autoScrollPinnedToBottom = true;
let activeChatPlotSrc = null;
const DEFAULT_MODEL = "openai/gpt-oss-120b";
const MODEL_STORAGE_KEY = "chat_model_name";
const API_KEY_STORAGE_KEY = "chat_api_key";

let sessionId = window.localStorage.getItem("chat_session_id");
if (!sessionId) {
  sessionId = crypto.randomUUID();
  window.localStorage.setItem("chat_session_id", sessionId);
}

function restoreModelSettings() {
  const savedModel = window.localStorage.getItem(MODEL_STORAGE_KEY);
  const savedApiKey = window.localStorage.getItem(API_KEY_STORAGE_KEY) || "";
  if (modelSelect) {
    const hasOption = Array.from(modelSelect.options).some((opt) => opt.value === savedModel);
    modelSelect.value = hasOption && savedModel ? savedModel : DEFAULT_MODEL;
  }
  if (apiKeyInput) {
    apiKeyInput.value = savedApiKey;
  }
}

function getSelectedModelName() {
  return modelSelect?.value || DEFAULT_MODEL;
}

function getApiKeyValue() {
  const value = apiKeyInput?.value || "";
  return value.trim();
}

function setNodeText(node, text) {
  if (!node) {
    return;
  }
  node.textContent = text;
}

function shouldKeepAutoScroll() {
  if (!chatPanel) {
    return true;
  }
  const distanceFromBottom = chatPanel.scrollHeight - chatPanel.scrollTop - chatPanel.clientHeight;
  return distanceFromBottom < 80;
}

function scrollChatToBottom(force = false) {
  if (!chatPanel) {
    return;
  }
  if (force || autoScrollPinnedToBottom) {
    chatPanel.scrollTop = chatPanel.scrollHeight;
  }
}

function closeChatPlotModal() {
  if (!chatPlotModal || !chatPlotModalImage) {
    return;
  }
  chatPlotModal.classList.add("hidden");
  chatPlotModal.setAttribute("aria-hidden", "true");
  chatPlotModalImage.removeAttribute("src");
  activeChatPlotSrc = null;
}

function openChatPlotModal(plotSrc) {
  if (!plotSrc || !chatPlotModal || !chatPlotModalImage) {
    return;
  }
  if (!chatPlotModal.classList.contains("hidden") && activeChatPlotSrc === plotSrc) {
    closeChatPlotModal();
    return;
  }
  activeChatPlotSrc = plotSrc;
  chatPlotModalImage.src = plotSrc;
  chatPlotModal.classList.remove("hidden");
  chatPlotModal.setAttribute("aria-hidden", "false");
}

function setAssistantBubbleContent(messageEl, text, plotUrl) {
  if (!messageEl) {
    return;
  }
  messageEl.classList.remove("loading");
  messageEl.innerHTML = `<div class="message-content">${marked.parse(text || "")}</div>`;
  if (plotUrl) {
    const isHtmlPlot = /\.html(?:\?|$)/i.test(plotUrl);
    if (isHtmlPlot) {
      const frame = document.createElement("iframe");
      frame.src = `${plotUrl}${plotUrl.includes("?") ? "&" : "?"}t=${Date.now()}`;
      frame.className = "chat-plot-iframe";
      frame.title = "Generated interactive plot";
      frame.loading = "lazy";
      frame.setAttribute("sandbox", "allow-scripts allow-same-origin");
      messageEl.appendChild(frame);
      return;
    }
    const hasInlineImage = Boolean(messageEl.querySelector(".message-content img"));
    if (hasInlineImage) {
      return;
    }
    const img = document.createElement("img");
    img.src = `${plotUrl}?t=${Date.now()}`;
    img.alt = "Generated tool plot";
    messageEl.appendChild(img);
  }
}

function appendMessage(role, text, plotUrl, forceScroll = false) {
  if (!chatPanel) {
    return null;
  }
  const wasAtBottom = shouldKeepAutoScroll();
  const messageEl = document.createElement("div");
  messageEl.className = `message ${role}`;

  if (role === "ai") {
    setAssistantBubbleContent(messageEl, text, plotUrl);
  } else {
    messageEl.textContent = text;
  }

  chatPanel.appendChild(messageEl);
  autoScrollPinnedToBottom = wasAtBottom;
  scrollChatToBottom(forceScroll);
  return messageEl;
}

function appendThinkingMessage() {
  if (!chatPanel) {
    return null;
  }
  const wasAtBottom = shouldKeepAutoScroll();
  const messageEl = document.createElement("div");
  messageEl.className = "message ai loading";
  messageEl.innerHTML =
    '<div class="thinking-indicator" aria-label="Assistant is thinking"><span></span><span></span><span></span></div>';
  chatPanel.appendChild(messageEl);
  autoScrollPinnedToBottom = wasAtBottom;
  scrollChatToBottom();
  return messageEl;
}

async function animateAssistantText(messageEl, fullText, plotUrl, renderToken) {
  if (!messageEl) {
    return;
  }
  const text = String(fullText || "");
  if (!text) {
    setAssistantBubbleContent(messageEl, "", plotUrl);
    return;
  }
  const chunkSize = 5;
  for (let index = chunkSize; index <= text.length; index += chunkSize) {
    if (renderToken !== activeRenderToken) {
      return;
    }
    setAssistantBubbleContent(messageEl, text.slice(0, index), null);
    scrollChatToBottom();
    await new Promise((resolve) => window.setTimeout(resolve, 14));
  }
  if (renderToken !== activeRenderToken) {
    return;
  }
  setAssistantBubbleContent(messageEl, text, plotUrl);
  scrollChatToBottom();
}

function setComposerState(state) {
  if (!chatForm || !sendButton || !input || !stopButton) {
    return;
  }
  const isLoading = state === "loading";
  chatForm.classList.toggle("loading", isLoading);
  chatForm.classList.toggle("typing", state === "typing");
  input.disabled = isLoading;
  if (modelSelect) {
    modelSelect.disabled = isLoading;
  }
  if (apiKeyInput) {
    apiKeyInput.disabled = isLoading;
  }
  sendButton.hidden = isLoading;
  stopButton.hidden = !isLoading;
  sendButton.disabled = isLoading || !input.value.trim();
}

function valueOrDash(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function buildPlotLayout(chart) {
  const baseLayout = chart?.plotly?.layout ? { ...chart.plotly.layout } : {};
  const traceCount = Array.isArray(chart?.plotly?.data) ? chart.plotly.data.length : 0;
  const axisItemCount = Array.isArray(chart?.plotly?.data?.[0]?.x) ? chart.plotly.data[0].x.length : 0;
  const isMonthlyVolumeChart = chart?.id === "monthly_campaign_volume_with_roi_ctr_cvr";

  baseLayout.font = {
    family: 'Inter, "Segoe UI", Arial, sans-serif',
    size: 10,
    color: "#334155",
    ...(baseLayout.font || {}),
  };

  baseLayout.hoverlabel = {
    bgcolor: "#ffffff",
    bordercolor: "#cbd5e1",
    font: { color: "#0f172a", size: 10 },
    ...(baseLayout.hoverlabel || {}),
  };

  baseLayout.margin = {
    l: 40,
    r: 28,
    t: 26,
    b: 46,
    ...(baseLayout.margin || {}),
  };

  if (baseLayout.xaxis) {
    baseLayout.xaxis = {
      automargin: true,
      tickangle: axisItemCount > 8 ? -28 : baseLayout.xaxis.tickangle,
      ...(baseLayout.xaxis || {}),
    };
  }

  if (baseLayout.yaxis) {
    baseLayout.yaxis = {
      automargin: true,
      ...(baseLayout.yaxis || {}),
    };
  }

  if (traceCount > 1) {
    baseLayout.legend = {
      ...(baseLayout.legend || {}),
      orientation: "h",
      x: 0,
      xanchor: "left",
      y: isMonthlyVolumeChart ? 1.14 : -0.28,
      yanchor: isMonthlyVolumeChart ? "bottom" : "top",
      bgcolor: isMonthlyVolumeChart ? "rgba(0,0,0,0)" : "rgba(255,255,255,0.86)",
      bordercolor: isMonthlyVolumeChart ? "rgba(0,0,0,0)" : "#e2e8f0",
      borderwidth: isMonthlyVolumeChart ? 0 : 1,
      font: { size: 9, color: "#334155" },
      entrywidth: isMonthlyVolumeChart ? 78 : undefined,
      entrywidthmode: isMonthlyVolumeChart ? "pixels" : undefined,
      tracegroupgap: isMonthlyVolumeChart ? 0 : undefined,
    };
    if (isMonthlyVolumeChart) {
      baseLayout.margin.t = Math.max(baseLayout.margin.t || 0, 64);
      baseLayout.margin.b = Math.max(baseLayout.margin.b || 0, 58);
    } else {
      baseLayout.margin.b = Math.max(baseLayout.margin.b || 0, 90);
    }
  }

  return baseLayout;
}

function setActiveTab(tabName) {
  if (
    !dashboardTab ||
    !pipelineTab ||
    !tracesTab ||
    !dashboardPanel ||
    !pipelinePanel ||
    !tracesPanel
  ) {
    return;
  }
  const isDashboard = tabName === "dashboard";
  const isPipeline = tabName === "pipeline";
  const isTraces = tabName === "traces";

  dashboardTab.classList.toggle("active", isDashboard);
  dashboardTab.setAttribute("aria-selected", String(isDashboard));
  pipelineTab.classList.toggle("active", isPipeline);
  pipelineTab.setAttribute("aria-selected", String(isPipeline));
  tracesTab.classList.toggle("active", isTraces);
  tracesTab.setAttribute("aria-selected", String(isTraces));

  dashboardPanel.classList.toggle("active", isDashboard);
  pipelinePanel.classList.toggle("active", isPipeline);
  tracesPanel.classList.toggle("active", isTraces);
}

function formatPipelineItems(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return "No pipeline logs yet.";
  }
  return items
    .map((item) => (item && typeof item.line === "string" ? item.line : ""))
    .filter((line) => line.length > 0)
    .join("\n");
}

function getSelectedChart() {
  if (!selectedChartId) {
    return null;
  }
  return dashboardCharts.find((chart) => chart.id === selectedChartId) || null;
}

function updateSelectedChartPill() {
  const selectedChart = getSelectedChart();
  if (!selectedChart) {
    setNodeText(selectedChartChatPill, "Chart context: None selected");
    return;
  }
  setNodeText(selectedChartChatPill, `Chart context: ${selectedChart.title}`);
}

function setSelectedChart(chartId) {
  selectedChartId = chartId || null;
  updateSelectedChartPill();
  Array.from(document.querySelectorAll(".chart-card")).forEach((card) => {
    card.classList.toggle("selected", Boolean(chartId) && card.dataset.chartId === chartId);
  });
}

function toggleSelectedChart(chartId) {
  if (!chartId) {
    setSelectedChart(null);
    return;
  }
  if (selectedChartId === chartId) {
    setSelectedChart(null);
    return;
  }
  setSelectedChart(chartId);
}

function createKpiCard(kpi) {
  const card = document.createElement("article");
  card.className = "kpi-card";

  const label = document.createElement("div");
  label.className = "kpi-label";
  label.textContent = valueOrDash(kpi?.label);

  const value = document.createElement("div");
  value.className = "kpi-value";
  value.textContent = valueOrDash(kpi?.value);

  const unit = document.createElement("span");
  unit.className = "kpi-unit";
  unit.textContent = valueOrDash(kpi?.unit);
  value.appendChild(unit);

  card.appendChild(label);
  card.appendChild(value);
  return card;
}

function renderDashboard(payload) {
  if (!kpiGrid || !dashboardChartGrid) {
    return;
  }
  const charts = Array.isArray(payload?.charts) ? payload.charts : [];
  const kpis = Array.isArray(payload?.kpis) ? payload.kpis : [];
  dashboardCharts = charts;

  kpiGrid.innerHTML = "";
  kpis.forEach((kpi) => {
    kpiGrid.appendChild(createKpiCard(kpi));
  });

  dashboardChartGrid.innerHTML = "";
  charts.forEach((chart) => {
    const card = document.createElement("article");
    card.className = "chart-card";
    card.dataset.chartId = chart.id;
    card.tabIndex = 0;

    const title = document.createElement("h3");
    title.className = "chart-title";
    title.textContent = valueOrDash(chart.title);

    const description = document.createElement("p");
    description.className = "chart-description";
    description.textContent = valueOrDash(chart.description);

    const plotContainer = document.createElement("div");
    plotContainer.className = "chart-canvas";
    plotContainer.id = `chart-${chart.id}`;

    card.appendChild(title);
    card.appendChild(description);
    card.appendChild(plotContainer);
    dashboardChartGrid.appendChild(card);

    card.addEventListener("click", () => toggleSelectedChart(chart.id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleSelectedChart(chart.id);
      }
    });

    Plotly.newPlot(plotContainer.id, chart.plotly?.data || [], buildPlotLayout(chart), {
      responsive: true,
      displayModeBar: false,
    });
    plotContainer.on("plotly_click", () => toggleSelectedChart(chart.id));
  });

  const hasCurrentSelection = charts.some((chart) => chart.id === selectedChartId);
  setSelectedChart(hasCurrentSelection ? selectedChartId : null);
}

function buildSelectedChartContext() {
  const selectedChart = getSelectedChart();
  if (!selectedChart) {
    return { selected_chart_id: null, selected_chart_context: null };
  }

  return {
    selected_chart_id: selectedChart.id,
    selected_chart_context: {
      title: selectedChart.title,
      description: selectedChart.description,
      chart_type: selectedChart.type,
      aggregation: selectedChart.chat_context?.aggregation || "",
      data_sample: selectedChart.chat_context?.data_sample || [],
    },
  };
}

async function fetchDashboard() {
  const response = await fetch("/api/dashboard");
  if (!response.ok) {
    throw new Error(`Dashboard fetch failed with status ${response.status}`);
  }
  return response.json();
}

async function refreshDashboard() {
  try {
    const data = await fetchDashboard();
    const signature = JSON.stringify(data || {});
    if (signature !== dashboardSignature) {
      renderDashboard(data);
      dashboardSignature = signature;
    }
  } catch (error) {
    if (kpiGrid) {
      kpiGrid.innerHTML = "";
    }
    if (dashboardChartGrid) {
      dashboardChartGrid.innerHTML = `<div class="chart-description">Unable to load dashboard: ${
        error.message || "unknown error"
      }</div>`;
    }
  }
}

function getTraceKey(item, index) {
  const details = item?.details || {};
  const msgIndex = details.index ?? "";
  return `${valueOrDash(item?.trace_id)}|${valueOrDash(item?.timestamp)}|${valueOrDash(
    item?.event
  )}|${msgIndex}|${index}`;
}

function createTraceEntry(item, index, openKeys) {
  const details = item?.details || {};
  const traceMessage = details.trace_message || {};
  const tokenUsage = traceMessage.token_usage || {};
  const totalTokens = valueOrDash(tokenUsage.total_tokens);
  const reasoningTokens = valueOrDash(traceMessage.reasoning_tokens);
  const role = valueOrDash(traceMessage.role);
  const event = valueOrDash(item?.event);
  const traceId = valueOrDash(item?.trace_id);
  const timestamp = valueOrDash(item?.timestamp);

  const wrapper = document.createElement("details");
  wrapper.className = "trace-item";
  const key = getTraceKey(item, index);
  wrapper.dataset.key = key;
  if (openKeys.has(key)) {
    wrapper.open = true;
  }

  const summary = document.createElement("summary");
  summary.textContent = `${index + 1}. ${timestamp} | event=${event} | role=${role} | total_tokens=${totalTokens} | reasoning_tokens=${reasoningTokens} | trace=${traceId}`;
  wrapper.appendChild(summary);

  const body = document.createElement("pre");
  body.className = "trace-body";
  body.textContent = JSON.stringify(item, null, 2);
  wrapper.appendChild(body);

  return wrapper;
}

function renderTraceItems(items) {
  if (!traceLogView) {
    return;
  }
  const openKeys = new Set(
    Array.from(traceLogView.querySelectorAll("details.trace-item[open]")).map(
      (element) => element.dataset.key
    )
  );
  const previousScrollTop = traceLogView.scrollTop;

  traceLogView.innerHTML = "";
  if (!Array.isArray(items) || items.length === 0) {
    traceLogView.textContent = "No model traces yet.";
    return;
  }

  items.forEach((item, index) => {
    traceLogView.appendChild(createTraceEntry(item, index, openKeys));
  });
  traceLogView.scrollTop = previousScrollTop;
}

async function sendMessage(message, signal) {
  const selectedContext = buildSelectedChartContext();
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal,
    body: JSON.stringify({
      session_id: sessionId,
      message,
      selected_chart_id: selectedContext.selected_chart_id,
      selected_chart_context: selectedContext.selected_chart_context,
      model_name: getSelectedModelName(),
      api_key: getApiKeyValue() || null,
    }),
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  const payloadText = await response.text();
  return JSON.parse(payloadText);
}

async function fetchLogStream(kind) {
  const response = await fetch(
    `/api/logs/${kind}?session_id=${encodeURIComponent(sessionId)}&limit=200`
  );
  if (!response.ok) {
    throw new Error(`Log fetch failed with status ${response.status}`);
  }
  return response.json();
}

async function refreshLogs() {
  if (!pipelineLogView || !traceLogView) {
    return;
  }
  try {
    const [pipelineData, traceData] = await Promise.all([
      fetchLogStream("pipeline"),
      fetchLogStream("traces"),
    ]);
    const pipelineText = formatPipelineItems(pipelineData.items);
    if (pipelineText !== lastPipelineText) {
      setNodeText(pipelineLogView, pipelineText);
      lastPipelineText = pipelineText;
    }

    const traceSignature = JSON.stringify(traceData.items || []);
    if (traceSignature !== lastTraceSignature) {
      renderTraceItems(traceData.items || []);
      lastTraceSignature = traceSignature;
    }
  } catch (error) {
    const text = `Unable to load logs: ${error.message || "unknown error"}`;
    setNodeText(pipelineLogView, text);
    setNodeText(traceLogView, text);
  }
}

if (chatPanel) {
  chatPanel.addEventListener("scroll", () => {
    autoScrollPinnedToBottom = shouldKeepAutoScroll();
  });
  chatPanel.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLImageElement)) {
      return;
    }
    if (!target.closest(".message.ai")) {
      return;
    }
    openChatPlotModal(target.currentSrc || target.src || "");
  });
}

if (chatPlotModalClose) {
  chatPlotModalClose.addEventListener("click", closeChatPlotModal);
}

if (chatPlotModalBackdrop) {
  chatPlotModalBackdrop.addEventListener("click", closeChatPlotModal);
}

if (chatPlotModalImage) {
  chatPlotModalImage.addEventListener("click", closeChatPlotModal);
}

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeChatPlotModal();
  }
});

if (chatForm && input && sendButton && stopButton) {
  if (modelSelect) {
    modelSelect.addEventListener("change", () => {
      window.localStorage.setItem(MODEL_STORAGE_KEY, getSelectedModelName());
    });
  }
  if (apiKeyInput) {
    apiKeyInput.addEventListener("input", () => {
      window.localStorage.setItem(API_KEY_STORAGE_KEY, apiKeyInput.value || "");
    });
  }

  input.addEventListener("input", () => {
    if (isGenerating) {
      return;
    }
    setComposerState(input.value.trim() ? "typing" : "idle");
  });

  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isGenerating) {
      return;
    }
    const message = input.value.trim();
    if (!message) return;

    appendMessage("user", message, null, true);
    input.value = "";
    isGenerating = true;
    setComposerState("loading");
    const thinkingEl = appendThinkingMessage();
    const renderToken = ++activeRenderToken;
    const controller = new AbortController();
    activeRequestController = controller;

    try {
      const data = await sendMessage(message, controller.signal);
      sessionId = data.session_id || sessionId;
      window.localStorage.setItem("chat_session_id", sessionId);
      await animateAssistantText(thinkingEl, data.assistant_text, data.plot_url, renderToken);
      await refreshLogs();
    } catch (error) {
      const isAborted = controller.signal.aborted || error.name === "AbortError";
      if (thinkingEl) {
        if (isAborted) {
          setAssistantBubbleContent(thinkingEl, "_Response stopped._");
        } else {
          setAssistantBubbleContent(thinkingEl, `Error: ${error.message || "Unable to reach backend."}`);
        }
      } else {
        appendMessage(
          "ai",
          isAborted ? "_Response stopped._" : `Error: ${error.message || "Unable to reach backend."}`
        );
      }
    } finally {
      if (activeRequestController === controller) {
        activeRequestController = null;
      }
      isGenerating = false;
      setComposerState(input.value.trim() ? "typing" : "idle");
      input.focus();
    }
  });

  stopButton.addEventListener("click", () => {
    if (!isGenerating) {
      return;
    }
    activeRenderToken += 1;
    if (activeRequestController) {
      activeRequestController.abort();
    }
  });
}

appendMessage(
  "ai",
  "Hello! Ask anything about the dataset.\nSelect any dashboard chart, then ask a chart-specific question in chat.",
  null,
  true
);
restoreModelSettings();
setComposerState("idle");

if (dashboardTab) {
  dashboardTab.addEventListener("click", () => setActiveTab("dashboard"));
}
if (pipelineTab) {
  pipelineTab.addEventListener("click", () => setActiveTab("pipeline"));
}
if (tracesTab) {
  tracesTab.addEventListener("click", () => setActiveTab("traces"));
}

setActiveTab("dashboard");
refreshDashboard();
refreshLogs();
setInterval(refreshDashboard, 60000);
setInterval(refreshLogs, 3000);
