const state = {
  devices: [],
  dashboardDevices: [],
  topologyEdges: [],
  topologySummary: {},
  dashboardFilter: "all",
  topologyFloorFilter: "all",
  topologyVendorFilter: "all",
  topologyTierFilter: "all",
  topologyZoom: 1,
  topologyAutoFit: false,
  topologyStreamStarted: false,
  topologyStreamStale: false,
  selectedDevice: null,
  selectedPurpose: "",
  latestPlan: null,
  selectedPort: null,
  latestPorts: [],
  latestPortSummary: {},
  portStatusFilter: "all",
  portModeFilter: "all",
  portVlanFilter: "",
  portSearchQuery: "",
  previewReady: false,
  previewAction: "collect",
  latestResult: null,
  rawOutput: "",
  rawSearchQuery: "",
  activeResultTab: "summary",
  activeDetailTab: "summary",
};

const page = document.body.dataset.page || "operations";

const nodes = {
  apiStatus: document.querySelector("#apiStatus"),
  dashboardUpdated: document.querySelector("#dashboardUpdated"),
  healthCards: document.querySelector("#healthCards"),
  topologyMap: document.querySelector("#topologyMap"),
  alarmFeed: document.querySelector("#alarmFeed"),
  dashboardShowAll: document.querySelector("#dashboardShowAll"),
  dashboardShowIssues: document.querySelector("#dashboardShowIssues"),
  devicesBody: document.querySelector("#devicesBody"),
  selectedDeviceId: document.querySelector("#selectedDeviceId"),
  deviceFacts: document.querySelector("#deviceFacts"),
  purposeSelect: document.querySelector("#purposeSelect"),
  checkDevice: document.querySelector("#checkDevice"),
  checkResults: document.querySelector("#checkResults"),
  loadPlan: document.querySelector("#loadPlan"),
  collect: document.querySelector("#collect"),
  commandPlan: document.querySelector("#commandPlan"),
  diagnosticSummary: document.querySelector("#diagnosticSummary"),
  diagnosticFindings: document.querySelector("#diagnosticFindings"),
  detailSeverity: document.querySelector("#detailSeverity"),
  commandPreview: document.querySelector("#commandPreview"),
  portMatrixMeta: document.querySelector("#portMatrixMeta"),
  portMatrixSummary: document.querySelector("#portMatrixSummary"),
  portMatrix: document.querySelector("#portMatrix"),
  portTableBody: document.querySelector("#portTableBody"),
  portRefresh: document.querySelector("#portRefresh"),
  portStatusFilter: document.querySelector("#portStatusFilter"),
  portModeFilter: document.querySelector("#portModeFilter"),
  portVlanFilter: document.querySelector("#portVlanFilter"),
  portSearchInput: document.querySelector("#portSearchInput"),
  portHealthSummary: document.querySelector("#portHealthSummary"),
  vlanMacSummary: document.querySelector("#vlanMacSummary"),
  collectionSummary: document.querySelector("#collectionSummary"),
  collectionMetrics: document.querySelector("#collectionMetrics"),
  resultMeta: document.querySelector("#resultMeta"),
  rawSearchInput: document.querySelector("#rawSearchInput"),
  copyRawOutput: document.querySelector("#copyRawOutput"),
  neighborsNote: document.querySelector("#neighborsNote"),
  neighborsBody: document.querySelector("#neighborsBody"),
  searchInput: document.querySelector("#searchInput"),
  searchButton: document.querySelector("#searchButton"),
  searchResultsBody: document.querySelector("#searchResultsBody"),
  diagnosePort: document.querySelector("#diagnosePort"),
  portDetailFacts: document.querySelector("#portDetailFacts"),
  portDetailState: document.querySelector("#portDetailState"),
  collectionResult: document.querySelector("#collectionResult"),
  auditBody: document.querySelector("#auditBody"),
  refreshDevices: document.querySelector("#refreshDevices"),
  refreshAudit: document.querySelector("#refreshAudit"),
};

const STATUS_COLOR = {
  normal: "#639922",
  ok: "#639922",
  warning: "#EF9F27",
  critical: "#E24B4A",
  fault: "#E24B4A",
  stale: "#888780",
  unreachable: "#888780",
};

const SEVERITY = {
  down: { label: "Down", rank: 8, title: "Service impact or unreachable state" },
  critical: { label: "Critical", rank: 7, title: "Immediate operator attention required" },
  warning: { label: "Warning", rank: 6, title: "Attention required" },
  unknown: { label: "Unknown", rank: 5, title: "State cannot be confirmed" },
  maintenance: { label: "Maintenance", rank: 4, title: "Planned maintenance or disabled state" },
  info: { label: "Info", rank: 3, title: "Informational state" },
  normal: { label: "Normal", rank: 2, title: "No current abnormal condition" },
  resolved: { label: "Resolved", rank: 1, title: "Issue has been resolved" },
};

const TOPOLOGY_LAYOUT = {
  nodeWidth: 220,
  nodeHeight: 112,
  nodeGap: 96,
  tierRowGap: 48,
  tierGap: 190,
  paddingX: 64,
  paddingY: 48,
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    ...options,
  });
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      payload = null;
    }
  }
  if (!response.ok) {
    const message = payload?.detail || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return payload;
}

function setStatus(message, ok = true) {
  if (!nodes.apiStatus) {
    return;
  }
  nodes.apiStatus.textContent = message;
  nodes.apiStatus.className = ok ? "status-ok" : "status-fail";
}

function text(value) {
  return value === null || value === undefined || value === "" ? "-" : String(value);
}

function isCollectable(device) {
  return Boolean(device?.collectable);
}

function normalizeSeverity(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "ok" || normalized === "connected" || normalized === "success") {
    return "normal";
  }
  if (normalized === "stale" || normalized === "unreachable" || normalized === "not_evaluated") {
    return "unknown";
  }
  if (normalized === "fail" || normalized === "error" || normalized === "fault") {
    return "critical";
  }
  return SEVERITY[normalized] ? normalized : "unknown";
}

function severityBadge(value, labelOverride) {
  const severity = normalizeSeverity(value);
  const badge = document.createElement("span");
  badge.className = `severity-badge severity-${severity}`;
  badge.title = SEVERITY[severity].title;
  const dot = document.createElement("span");
  dot.className = "severity-dot";
  badge.append(dot, document.createTextNode(labelOverride || SEVERITY[severity].label));
  return badge;
}

function setSeverityBadge(node, value, labelOverride) {
  if (!node) {
    return;
  }
  node.replaceChildren(...severityBadge(value, labelOverride).childNodes);
  node.className = `severity-badge severity-${normalizeSeverity(value)}`;
  node.title = SEVERITY[normalizeSeverity(value)].title;
}

function deviceStatus(device) {
  const row = state.dashboardDevices.find((item) => item.device.device_id === device?.device_id);
  if (!row) {
    return isCollectable(device) ? "info" : "unknown";
  }
  return normalizeSeverity(dashboardStatus(row));
}

function portSeverity(port) {
  if (!port) {
    return "unknown";
  }
  if (hasPortErrors(port)) {
    return "critical";
  }
  const status = String(port.status || "").toLowerCase();
  if (["errdisabled"].includes(status)) {
    return "critical";
  }
  if (["notconnect", "down"].includes(status)) {
    return "down";
  }
  if (["disabled"].includes(status)) {
    return "maintenance";
  }
  if (!status) {
    return "unknown";
  }
  return "normal";
}

function hasPortErrors(port) {
  return (
    Number(port?.fcs_errors || 0) > 0 ||
    Number(port?.rx_errors || 0) > 0 ||
    Number(port?.runts || 0) > 0 ||
    Number(port?.tx_errors || 0) > 0 ||
    Number(port?.align_errors || 0) > 0 ||
    Number(port?.symbol_errors || 0) > 0
  );
}

function portMode(port) {
  const vlan = String(port?.vlan || "").toLowerCase();
  const description = String(port?.description || "").toLowerCase();
  if (vlan.includes("trunk") || vlan === "routed" || description.includes("trunk") || description.includes("uplink")) {
    return "trunk";
  }
  return "access";
}

function renderDevices() {
  if (!nodes.devicesBody) {
    return;
  }
  nodes.devicesBody.replaceChildren();
  for (const device of state.devices) {
    const row = document.createElement("tr");
    row.className = "device-row";
    row.dataset.deviceId = device.device_id;
    if (state.selectedDevice?.device_id === device.device_id) {
      row.classList.add("selected");
    }
    const statusCell = document.createElement("td");
    statusCell.append(severityBadge(deviceStatus(device)));
    row.append(statusCell);
    appendCells(row, [
      device.device_id,
      device.hostname,
      device.management_ip,
      device.vendor,
      device.platform,
      device.role,
      device.access_method,
    ]);
    row.addEventListener("click", () => selectDevice(device.device_id));
    nodes.devicesBody.append(row);
  }
}

function renderDeviceFacts(device) {
  if (!nodes.selectedDeviceId || !nodes.deviceFacts) {
    if (nodes.selectedDeviceId) {
      nodes.selectedDeviceId.textContent = device ? device.device_id : "No device selected";
    }
    return;
  }
  nodes.selectedDeviceId.textContent = device ? device.device_id : "No device selected";
  nodes.deviceFacts.replaceChildren();
  if (!device) {
    setSeverityBadge(nodes.detailSeverity, "unknown");
    return;
  }
  setSeverityBadge(nodes.detailSeverity, deviceStatus(device));

  const facts = [
    ["Hostname", device.hostname],
    ["Management IP", device.management_ip],
    ["Vendor", device.vendor],
    ["Platform", device.platform],
    ["Role", device.role],
    ["Access", device.access_method],
    ["Notes", device.notes],
  ];

  for (const [label, value] of facts) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = text(value);
    nodes.deviceFacts.append(dt, dd);
  }
}

async function loadDevices() {
  setStatus("Loading inventory...", true);
  state.devices = await api("/devices");
  if (!state.selectedDevice && state.devices.length && page !== "dashboard") {
    state.selectedDevice = state.devices[0];
  } else if (state.selectedDevice) {
    state.selectedDevice = state.devices.find((item) => item.device_id === state.selectedDevice.device_id) || null;
  }
  renderDevices();
  renderDeviceFacts(state.selectedDevice);
  renderCheckResults(null);
  updateCheckButton();
  await loadDashboard();
  await loadDiagnostics();
  await loadNeighbors();
  await loadPurposes();
  await loadPorts();
  renderPortDetail(null);
  renderDiagnosticResult(null);
  setStatus(`API connected. ${state.devices.length} devices loaded.`, true);
}

async function selectDevice(deviceId) {
  state.selectedDevice =
    state.devices.find((device) => device.device_id === deviceId) ||
    state.dashboardDevices.find((row) => row.device.device_id === deviceId)?.device ||
    null;
  state.latestPlan = null;
  state.selectedPort = null;
  state.previewReady = false;
  state.previewAction = "collect";
  renderDevices();
  renderDashboard();
  renderDeviceFacts(state.selectedDevice);
  renderCommandPlan(null);
  renderPortDetail(null);
  renderCheckResults(null);
  updateCheckButton();
  await loadDiagnostics();
  await loadNeighbors();
  await loadPurposes();
  await loadPorts();
  setCollectionResultText(collectionReadyMessage(state.selectedDevice));
  renderDiagnosticResult(null);
}

function updateCheckButton() {
  if (!nodes.checkDevice) {
    return;
  }
  nodes.checkDevice.disabled = !isCollectable(state.selectedDevice);
  nodes.checkDevice.textContent = "Preview CHECK";
}

async function loadPurposes() {
  if (!nodes.purposeSelect || !nodes.loadPlan || !nodes.collect) {
    return;
  }
  nodes.purposeSelect.replaceChildren();
  state.selectedPurpose = "";
  nodes.purposeSelect.disabled = true;
  nodes.loadPlan.disabled = true;
  nodes.collect.disabled = true;

  if (!state.selectedDevice) {
    return;
  }

  const payload = await api(`/vendors/${encodeURIComponent(state.selectedDevice.vendor)}/purposes`);
  for (const purpose of payload.purposes) {
    const option = document.createElement("option");
    option.value = purpose;
    option.textContent = purpose;
    nodes.purposeSelect.append(option);
  }
  state.selectedPurpose = payload.purposes[0] || "";
  nodes.purposeSelect.value = state.selectedPurpose;
  nodes.purposeSelect.disabled = !state.selectedPurpose;
  nodes.loadPlan.disabled = !state.selectedPurpose;
  nodes.collect.disabled = true;
  state.previewReady = false;
  state.previewAction = "collect";
  if (state.selectedPurpose) {
    await loadCommandPlan();
  }
}

async function loadCommandPlan() {
  if (!nodes.collect) {
    return;
  }
  if (!state.selectedDevice || !state.selectedPurpose) {
    return;
  }
  state.latestPlan = await api(
    `/devices/${encodeURIComponent(state.selectedDevice.device_id)}/command-plan/${encodeURIComponent(state.selectedPurpose)}`,
  );
  renderCommandPlan(state.latestPlan);
  renderCommandPreview(state.latestPlan, { action: "collect" });
}

function renderCommandPlan(plan) {
  if (!nodes.commandPlan) {
    return;
  }
  nodes.commandPlan.replaceChildren();
  if (!plan) {
    return;
  }
  for (const command of plan.commands) {
    const item = document.createElement("li");
    item.textContent = command;
    nodes.commandPlan.append(item);
  }
}

function renderCommandPreview(plan, { action = "collect", port = state.selectedPort } = {}) {
  state.previewAction = action;
  state.previewReady = Boolean(
    state.selectedDevice &&
    isCollectable(state.selectedDevice) &&
    plan &&
    Array.isArray(plan.commands) &&
    plan.commands.length &&
    plan.read_only !== false,
  );
  if (nodes.collect) {
    nodes.collect.textContent = action === "check" ? "Run CHECK" : "Run Diagnostic";
    nodes.collect.disabled = !state.previewReady;
  }
  if (!nodes.commandPreview) {
    return;
  }
  nodes.commandPreview.replaceChildren();
  if (!state.selectedDevice) {
    nodes.commandPreview.className = "command-preview empty-state";
    nodes.commandPreview.textContent = "Select a device and purpose to preview read-only commands before execution.";
    return;
  }
  if (!plan) {
    nodes.commandPreview.className = "command-preview empty-state";
    nodes.commandPreview.textContent = "Generate a command preview before running diagnostics.";
    return;
  }

  nodes.commandPreview.className = `command-preview ${state.previewReady ? "safe" : "blocked"}`;
  const header = document.createElement("div");
  header.className = "preview-header";
  header.append(
    severityBadge(state.previewReady ? "info" : "critical", state.previewReady ? "Read-only / Safe" : "Blocked"),
  );
  const title = document.createElement("strong");
  title.textContent = action === "check" ? "One-click Network CHECK Preview" : "Diagnostic Execution Preview";
  header.prepend(title);

  const facts = document.createElement("dl");
  facts.className = "preview-facts";
  const expected = expectedOutputForPurpose(action === "check" ? "check" : plan.purpose);
  const rows = [
    ["Target Device", state.selectedDevice.device_id],
    ["Management IP", state.selectedDevice.management_ip],
    ["Target Port", port?.interface || "Device scope"],
    ["Purpose", action === "check" ? "check" : plan.purpose],
    ["Risk Level", plan.read_only === false ? "Blocked" : "Read-only / Safe Diagnostic"],
    ["Expected Output", expected],
    ["Estimated Time", action === "check" ? "30-90 seconds" : "10-45 seconds"],
    ["Audit Logging", "Enabled after execution"],
  ];
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = text(value);
    facts.append(dt, dd);
  }

  const notice = document.createElement("p");
  notice.className = "safety-notice";
  notice.textContent = "This diagnostic will run read-only commands only. No configuration changes will be made.";

  nodes.commandPreview.append(header, facts, notice);
}

function expectedOutputForPurpose(purpose) {
  const map = {
    check: "Interface status, error counters, endpoint correlation, topology and switching observations",
    interfaces: "Interface status, speed/duplex, descriptions, and error counters",
    endpoints: "Interface descriptions, MAC table, and ARP correlation",
    "port-endpoints": "Port status, descriptions, MAC addresses, and ARP correlation",
    topology: "CDP/LLDP neighbor relationships and link evidence",
    switching: "VLAN, trunk, spanning-tree, MAC table, and switching state",
    baseline: "Version, hostname, interface overview, and baseline inventory evidence",
    "security-logs": "Logging and user-session evidence",
  };
  return map[purpose] || "Read-only command output and parsed diagnostic evidence";
}

async function checkSelectedDevice() {
  if (!nodes.checkDevice) {
    return;
  }
  if (!state.selectedDevice) {
    return;
  }
  if (!isCollectable(state.selectedDevice)) {
    renderCheckResults([{
      label: "CHECK",
      status: "fail",
      detail: "This device is not enabled for read-only collection.",
    }]);
    return;
  }
  if (state.previewAction !== "check" || !state.previewReady) {
    const plan = await buildCheckPreviewPlan();
    state.latestPlan = plan;
    renderCommandPlan(plan);
    renderCommandPreview(plan, { action: "check" });
    nodes.checkDevice.textContent = "CHECK Preview Ready";
    renderSummary("CHECK preview is ready. Review the target and commands, then click Run CHECK in the detail panel.", "warn");
    activateDetailTab("diagnostics");
    return;
  }

  nodes.checkDevice.disabled = true;
  if (nodes.collect) {
    nodes.collect.disabled = true;
  }
  state.selectedPurpose = "check";
  state.previewReady = false;
  renderCheckResults([{
    label: "CHECK",
    status: "unknown",
    detail: "Running allowlisted read-only interface, endpoint, topology, and switching checks...",
  }]);
  setCollectionResultText("Running one-click read-only network check...");
  renderSummary("CHECK request in progress.", "warn");

  try {
    const result = await api(
      `/devices/${encodeURIComponent(state.selectedDevice.device_id)}/check`,
      { method: "POST" },
    );
    renderCheckResults(result.check_items);
    setCollectionResultHtml(formatCheckResultHtml(result));
    renderDiagnosticResult(result);
    renderSummary(
      result.success ? "CHECK completed. Review the Network Check results." : `CHECK failed. ${text(result.error_summary)}`,
      result.success ? "ok" : "error",
    );
  } catch (error) {
    renderCheckResults([{
      label: "CHECK",
      status: "fail",
      detail: error.message,
    }]);
    setCollectionResultHtml(escapeHtml(formatCollectionError(error)));
    renderDiagnosticResult({
      success: false,
      device_id: state.selectedDevice.device_id,
      management_ip: state.selectedDevice.management_ip,
      purpose: "check",
      commands: state.latestPlan?.commands || [],
      error_summary: error.message,
      stdout: "",
      stderr: "",
      parsed_ports: [],
      interface_findings: {},
    });
    renderSummary(error.message, "error");
  } finally {
    updateCheckButton();
    if (nodes.collect) {
      nodes.collect.disabled = true;
    }
    await loadAudit();
    await loadDashboard();
    await loadDiagnostics();
    await loadPorts();
  }
}

async function buildCheckPreviewPlan() {
  const preferredPurposes = ["interfaces", "endpoints", "topology", "switching"];
  const available = Array.from(nodes.purposeSelect?.options || []).map((option) => option.value);
  const purposes = preferredPurposes.filter((purpose) => available.includes(purpose));
  const commands = [];
  const seen = new Set();
  for (const purpose of purposes) {
    try {
      const plan = await api(
        `/devices/${encodeURIComponent(state.selectedDevice.device_id)}/command-plan/${encodeURIComponent(purpose)}`,
      );
      for (const command of plan.commands || []) {
        if (!seen.has(command)) {
          seen.add(command);
          commands.push(command);
        }
      }
    } catch {
      // Skip unavailable preview fragments; backend execution still enforces policy.
    }
  }
  return {
    device: state.selectedDevice,
    purpose: "check",
    commands,
    read_only: commands.length > 0,
  };
}

function renderCheckResults(items) {
  if (!nodes.checkResults) {
    return;
  }
  nodes.checkResults.replaceChildren();
  const rows = items || [
    { label: "저속 협상 포트 자동 탐지", status: "unknown", detail: "CHECK를 실행하면 결과가 표시됩니다." },
    { label: "CRC/error 많은 포트 탐지", status: "unknown", detail: "CHECK를 실행하면 결과가 표시됩니다." },
    { label: "uplink/LACP/trunk 자동 판정", status: "not_evaluated", detail: "CHECK 실행 후 자동 판정 가능 여부가 표시됩니다." },
    { label: "IP-MAC-Port 자동 추적", status: "unknown", detail: "CHECK를 실행하면 결과가 표시됩니다." },
    { label: "구성도와 실제 연결 상태 불일치 탐지", status: "unknown", detail: "CHECK를 실행하면 결과가 표시됩니다." },
  ];
  for (const item of rows) {
    const article = document.createElement("article");
    const status = checkStatus(item.status);
    article.className = `check-item ${status}`;

    const statusNode = document.createElement("div");
    statusNode.className = "check-status";
    statusNode.append(severityBadge(checkSeverity(status), checkStatusLabel(status)));

    const labelNode = document.createElement("div");
    labelNode.className = "check-label";
    labelNode.textContent = item.label;

    const detailNode = document.createElement("div");
    detailNode.className = "check-detail";
    detailNode.textContent = item.detail;

    article.append(statusNode, labelNode, detailNode);
    nodes.checkResults.append(article);
  }
}

function checkStatus(status) {
  return ["ok", "warn", "fail", "unknown", "not_evaluated"].includes(status) ? status : "unknown";
}

function checkStatusLabel(status) {
  return status === "not_evaluated" ? "not evaluated" : status;
}

function checkSeverity(status) {
  if (status === "ok") {
    return "normal";
  }
  if (status === "warn") {
    return "warning";
  }
  if (status === "fail") {
    return "critical";
  }
  return "unknown";
}

async function runSearch() {
  if (!nodes.searchInput || !nodes.searchResultsBody) {
    return;
  }
  const query = nodes.searchInput.value.trim();
  nodes.searchResultsBody.replaceChildren();
  if (!query) {
    appendEmptySearchRow("Enter a device, port, IP, or MAC search.");
    return;
  }

  const payload = await api(`/search?q=${encodeURIComponent(query)}`);
  if (!payload.results.length) {
    appendEmptySearchRow("No parsed or reference matches.");
    return;
  }

  for (const result of payload.results) {
    const row = document.createElement("tr");
    row.className = "search-result-row";
    appendCells(row, [
      result.type,
      result.label,
      result.source,
      result.summary,
    ]);
    row.addEventListener("click", () => openSearchResult(result));
    nodes.searchResultsBody.append(row);
  }
}

function appendEmptySearchRow(message) {
  if (!nodes.searchResultsBody) {
    return;
  }
  const row = document.createElement("tr");
  const cell = document.createElement("td");
  cell.colSpan = 4;
  cell.className = "muted empty-cell";
  cell.textContent = message;
  row.append(cell);
  nodes.searchResultsBody.append(row);
}

async function openSearchResult(result) {
  if (result.device_id) {
    await selectDevice(result.device_id);
  }
  if (result.type === "port" && result.device_id && result.interface) {
    await loadPortDetail(result.device_id, result.interface);
    document.querySelector(".detail-panel")?.scrollIntoView({ block: "start", behavior: "smooth" });
    return;
  }
  if (result.type === "neighbor") {
    renderReferencePortDetail(result);
    document.querySelector(".detail-panel")?.scrollIntoView({ block: "start", behavior: "smooth" });
  }
}

async function loadPortDetail(deviceId, interfaceName) {
  const payload = await api(
    `/devices/${encodeURIComponent(deviceId)}/ports/${encodeURIComponent(interfaceName)}/latest`,
  );
  if (!payload.data_available) {
    renderPortDetail(null, payload.message || "No stored parsed observation for this port yet.");
    return;
  }
  renderPortDetail(payload.port);
}

async function loadPorts() {
  if (!nodes.portMatrix && !nodes.portTableBody) {
    return;
  }
  state.latestPorts = [];
  state.latestPortSummary = {};
  nodes.portMatrix?.replaceChildren();
  nodes.portTableBody?.replaceChildren();
  nodes.portMatrixSummary?.replaceChildren();
  if (!state.selectedDevice) {
    if (nodes.portMatrixMeta) {
      nodes.portMatrixMeta.textContent = "Select a device to load latest parsed port state.";
    }
    renderPortEmptyState("No device selected.");
    return;
  }
  if (nodes.portMatrixMeta) {
    nodes.portMatrixMeta.textContent = `Loading ports for ${state.selectedDevice.device_id}...`;
  }
  try {
    const payload = await api(`/devices/${encodeURIComponent(state.selectedDevice.device_id)}/ports/latest`);
    state.latestPorts = (Array.isArray(payload.ports) ? payload.ports : []).filter((port) =>
      looksLikePortInterface(port?.interface),
    );
    state.latestPortSummary = payload.summary || {};
    if (nodes.portMatrixMeta) {
      nodes.portMatrixMeta.textContent = payload.data_available
        ? `${state.selectedDevice.hostname} (${state.selectedDevice.management_ip}) - ${text(payload.timestamp)}`
        : payload.message || "No stored parsed observation yet.";
    }
    renderPortMatrix();
  } catch (error) {
    if (nodes.portMatrixMeta) {
      nodes.portMatrixMeta.textContent = error.message;
    }
    renderPortEmptyState("Port state could not be loaded.");
  }
}

function renderPortMatrix() {
  renderPortSummary();
  renderPortTiles();
  renderPortTable();
}

function renderPortSummary() {
  if (!nodes.portMatrixSummary) {
    return;
  }
  const ports = state.latestPorts;
  const counts = {
    total: ports.length,
    up: ports.filter((port) => portSeverity(port) === "normal").length,
    down: ports.filter((port) => portSeverity(port) === "down").length,
    error: ports.filter((port) => portSeverity(port) === "critical").length,
    disabled: ports.filter((port) => portSeverity(port) === "maintenance").length,
    trunk: ports.filter((port) => portMode(port) === "trunk").length,
    access: ports.filter((port) => portMode(port) === "access").length,
  };
  const metrics = [
    ["Total Ports", counts.total, "info"],
    ["Up", counts.up, "normal"],
    ["Down", counts.down, "down"],
    ["Error", counts.error, "critical"],
    ["Disabled", counts.disabled, "maintenance"],
    ["Trunk", counts.trunk, "info"],
    ["Access", counts.access, "normal"],
  ];
  nodes.portMatrixSummary.replaceChildren();
  for (const [label, value, severity] of metrics) {
    const item = document.createElement("div");
    item.className = `metric-card metric-${normalizeSeverity(severity)}`;
    const valueNode = document.createElement("strong");
    valueNode.textContent = value;
    const labelNode = document.createElement("span");
    labelNode.textContent = label;
    item.append(valueNode, labelNode);
    nodes.portMatrixSummary.append(item);
  }
}

function renderPortTiles() {
  if (!nodes.portMatrix) {
    return;
  }
  nodes.portMatrix.replaceChildren();
  const ports = filteredPorts();
  if (!state.latestPorts.length) {
    renderPortEmptyState("No parsed ports found. Run a read-only interface collection first.");
    return;
  }
  if (!ports.length) {
    renderPortEmptyState("No ports match the current filters.");
    return;
  }
  for (const port of ports) {
    const button = document.createElement("button");
    const severity = portSeverity(port);
    button.type = "button";
    button.className = `port-tile severity-${severity}`;
    button.dataset.interface = port.interface;
    if (state.selectedPort?.interface === port.interface) {
      button.classList.add("selected");
    }
    button.title = portTooltip(port);
    const name = document.createElement("span");
    name.className = "port-name";
    name.textContent = shortInterfaceName(port.interface);
    const status = document.createElement("span");
    status.className = "port-status";
    status.textContent = portTileLabel(port);
    const mode = document.createElement("span");
    mode.className = "port-mode";
    mode.textContent = portMode(port);
    button.append(name, status, mode);
    button.addEventListener("click", () => {
      renderPortDetail(port);
      renderPortMatrix();
      activateDetailTab("summary");
    });
    nodes.portMatrix.append(button);
  }
}

function renderPortTable() {
  if (!nodes.portTableBody) {
    return;
  }
  nodes.portTableBody.replaceChildren();
  for (const port of filteredPorts()) {
    const row = document.createElement("tr");
    row.className = "port-table-row";
    row.addEventListener("click", () => {
      renderPortDetail(port);
      renderPortMatrix();
      activateDetailTab("summary");
    });
    const statusCell = document.createElement("td");
    statusCell.append(severityBadge(portSeverity(port), portTileLabel(port)));
    appendCells(row, [
      shortInterfaceName(port.interface),
    ]);
    row.insertBefore(statusCell, row.children[1] || null);
    appendCells(row, [
      portMode(port),
      port.vlan,
      port.speed,
      port.duplex,
      port.fcs_errors || 0,
      port.rx_errors || 0,
      Array.isArray(port.endpoint_macs) ? port.endpoint_macs.length : 0,
      port.description,
    ]);
    nodes.portTableBody.append(row);
  }
}

function renderPortEmptyState(message) {
  if (!nodes.portMatrix) {
    return;
  }
  nodes.portMatrix.replaceChildren();
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = message;
  nodes.portMatrix.append(empty);
}

function filteredPorts() {
  return state.latestPorts.filter((port) => {
    const severity = portSeverity(port);
    if (state.portStatusFilter !== "all") {
      const matchesStatus =
        (state.portStatusFilter === "error" && severity === "critical") ||
        (state.portStatusFilter === "down" && severity === "down") ||
        (state.portStatusFilter === "disabled" && severity === "maintenance") ||
        (state.portStatusFilter === "up" && severity === "normal") ||
        (state.portStatusFilter === "unknown" && severity === "unknown");
      if (!matchesStatus) {
        return false;
      }
    }
    if (state.portModeFilter !== "all" && portMode(port) !== state.portModeFilter) {
      return false;
    }
    if (state.portVlanFilter && !String(port.vlan || "").toLowerCase().includes(state.portVlanFilter)) {
      return false;
    }
    if (state.portSearchQuery) {
      const haystack = [
        port.interface,
        port.description,
        port.status,
        port.speed,
        port.duplex,
        port.neighbor_name,
        port.neighbor_ip,
      ].join(" ").toLowerCase();
      if (!haystack.includes(state.portSearchQuery)) {
        return false;
      }
    }
    return true;
  });
}

function portTileLabel(port) {
  const severity = portSeverity(port);
  if (severity === "critical") {
    return hasPortErrors(port) ? "ERR" : "CRIT";
  }
  if (severity === "down") {
    return "DOWN";
  }
  if (severity === "maintenance") {
    return "DIS";
  }
  if (severity === "unknown") {
    return "UNK";
  }
  return "UP";
}

function looksLikePortInterface(value) {
  const textValue = String(value || "").trim();
  if (!textValue || /[\s,]/.test(textValue)) {
    return false;
  }
  return /^(Et|Ethernet|Gi|GigabitEthernet|Te|TenGigabitEthernet|Fa|FastEthernet)\d+(?:\/\d+)*(?:\.\d+)?$|^(Po|Port-channel|Port-Channel)\d+$/i.test(textValue);
}

function portTooltip(port) {
  return [
    `Port: ${text(port.interface)}`,
    `Status: ${text(port.status)}`,
    `VLAN: ${text(port.vlan)}`,
    `Mode: ${portMode(port)}`,
    `Speed / Duplex: ${text(port.speed)} / ${text(port.duplex)}`,
    `Description: ${text(port.description)}`,
    `Last Change: ${text(port.source_timestamp)}`,
    `CRC/FCS Errors: ${port.fcs_errors || 0}`,
    `Input/Rx Errors: ${port.rx_errors || 0}`,
    `Connected MAC Count: ${Array.isArray(port.endpoint_macs) ? port.endpoint_macs.length : 0}`,
  ].join("\n");
}

function renderPortDetail(port, message = "Search for a port, IP, MAC, or device to inspect stored parsed state.") {
  if (!nodes.portDetailFacts || !nodes.portDetailState || !nodes.diagnosePort) {
    state.selectedPort = port;
    return;
  }
  state.selectedPort = port;
  nodes.portDetailFacts.replaceChildren();
  nodes.diagnosePort.disabled = !state.selectedDevice || !port;
  if (!port) {
    nodes.portDetailState.className = "summary-box warn";
    nodes.portDetailState.textContent = message;
    nodes.portHealthSummary && (nodes.portHealthSummary.textContent = "Select a port to review counters and status.");
    nodes.vlanMacSummary && (nodes.vlanMacSummary.textContent = "Select a parsed port to inspect VLAN, mode, endpoints, and neighbors.");
    setSeverityBadge(nodes.detailSeverity, state.selectedDevice ? deviceStatus(state.selectedDevice) : "unknown");
    return;
  }
  setSeverityBadge(nodes.detailSeverity, portSeverity(port), `${shortInterfaceName(port.interface)} ${SEVERITY[portSeverity(port)].label}`);

  const facts = [
    ["Interface", port.interface],
    ["Status", port.status],
    ["Mode", portMode(port)],
    ["VLAN", port.vlan],
    ["Speed / Duplex", `${text(port.speed)} / ${text(port.duplex)}`],
    ["Description", port.description],
    ["Endpoint IPs", listText(port.endpoint_ips)],
    ["Endpoint MACs", listText(port.endpoint_macs)],
    ["Neighbor", port.neighbor_name],
    ["Neighbor IP", port.neighbor_ip],
    ["Neighbor Platform", port.neighbor_platform],
    ["Errors", `FCS=${port.fcs_errors || 0}, Rx=${port.rx_errors || 0}, Runts=${port.runts || 0}, Tx=${port.tx_errors || 0}`],
    ["Source", `${text(port.source_purpose)} ${text(port.source_timestamp)}`],
    ["Recent Changes", "No stored history yet."],
  ];

  for (const [label, value] of facts) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = text(value);
    nodes.portDetailFacts.append(dt, dd);
  }
  nodes.portDetailState.className = "summary-box ok";
  nodes.portDetailState.textContent = "Stored parsed observation loaded. Documentation/reference data is not treated as live truth.";
  renderPortAuxiliaryDetail(port);
}

function renderPortAuxiliaryDetail(port) {
  if (nodes.portHealthSummary) {
    nodes.portHealthSummary.replaceChildren();
    const list = document.createElement("dl");
    list.className = "facts compact-facts";
    const rows = [
      ["Operational Status", port.status],
      ["Speed / Duplex", `${text(port.speed)} / ${text(port.duplex)}`],
      ["CRC/FCS Errors", port.fcs_errors || 0],
      ["Input/Rx Errors", port.rx_errors || 0],
      ["Runts", port.runts || 0],
      ["Tx Errors", port.tx_errors || 0],
      ["Last Observed", port.source_timestamp],
    ];
    for (const [label, value] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = text(value);
      list.append(dt, dd);
    }
    nodes.portHealthSummary.className = "detail-section";
    nodes.portHealthSummary.append(list);
  }
  if (nodes.vlanMacSummary) {
    nodes.vlanMacSummary.replaceChildren();
    const list = document.createElement("dl");
    list.className = "facts compact-facts";
    const rows = [
      ["VLAN", port.vlan],
      ["Mode", portMode(port)],
      ["Endpoint IPs", listText(port.endpoint_ips)],
      ["Endpoint MACs", listText(port.endpoint_macs)],
      ["Connected MAC Count", Array.isArray(port.endpoint_macs) ? port.endpoint_macs.length : 0],
      ["Neighbor", port.neighbor_name],
      ["Neighbor IP", port.neighbor_ip],
      ["Neighbor Platform", port.neighbor_platform],
    ];
    for (const [label, value] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = text(value);
      list.append(dt, dd);
    }
    nodes.vlanMacSummary.className = "detail-section";
    nodes.vlanMacSummary.append(list);
  }
}

function renderReferencePortDetail(result) {
  if (!nodes.portDetailFacts || !nodes.portDetailState || !nodes.diagnosePort) {
    state.selectedPort = null;
    return;
  }
  state.selectedPort = null;
  nodes.portDetailFacts.replaceChildren();
  nodes.diagnosePort.disabled = !state.selectedDevice;
  setSeverityBadge(nodes.detailSeverity, "unknown", "Reference");
  const facts = [
    ["Interface", result.interface],
    ["Reference Target", result.label],
    ["Source", result.source],
    ["Summary", result.summary],
    ["Recent Changes", "No stored history yet."],
  ];
  for (const [label, value] of facts) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = text(value);
    nodes.portDetailFacts.append(dt, dd);
  }
  nodes.portDetailState.className = "summary-box warn";
  nodes.portDetailState.textContent = "Reference match only. Run read-only collection before treating this as live state.";
  nodes.portHealthSummary && (nodes.portHealthSummary.textContent = "Reference match only. Run collection before using health counters.");
  nodes.vlanMacSummary && (nodes.vlanMacSummary.textContent = "Reference match only. Live VLAN/MAC state is not available.");
}

async function diagnoseSelectedPort() {
  if (!nodes.purposeSelect || !nodes.collect) {
    return;
  }
  if (!state.selectedDevice) {
    return;
  }
  const options = Array.from(nodes.purposeSelect.options).map((option) => option.value);
  if (!options.includes("interfaces")) {
    renderSummary("No allowlisted interfaces purpose is available for this device.", "error");
    return;
  }
  state.selectedPurpose = "interfaces";
  nodes.purposeSelect.value = "interfaces";
  await loadCommandPlan();
  renderSummary("Port diagnostic preview loaded. Review the target, risk level, and commands before running diagnostics.", "warn");
  activateDetailTab("diagnostics");
}

function listText(values) {
  return Array.isArray(values) && values.length ? values.join(", ") : "-";
}

async function collectSelected() {
  if (!nodes.collect) {
    return;
  }
  if (state.previewAction === "check") {
    await checkSelectedDevice();
    return;
  }
  if (!state.selectedDevice || !state.selectedPurpose) {
    return;
  }
  if (!isCollectable(state.selectedDevice)) {
    renderSummary("Collection is disabled until this device access method and credentials are verified.", "warn");
    return;
  }
  if (!state.previewReady || !state.latestPlan) {
    if (state.latestPlan) {
      renderCommandPreview(state.latestPlan, { action: "collect" });
    }
    renderSummary("Review the command preview before running diagnostics.", "warn");
    activateDetailTab("diagnostics");
    return;
  }

  nodes.collect.disabled = true;
  state.previewReady = false;
  setCollectionResultText("Collecting read-only command metadata...");
  renderSummary("Collection request in progress.", "warn");

  try {
    const result = await api(
      `/devices/${encodeURIComponent(state.selectedDevice.device_id)}/collect/${encodeURIComponent(state.selectedPurpose)}`,
      { method: "POST" },
    );
    setCollectionResultHtml(formatCollectionResultHtml(result));
    renderDiagnosticResult(result);
    renderSummary(summaryFromResult(result), result.success ? "ok" : "error");
  } catch (error) {
    setCollectionResultHtml(escapeHtml(formatCollectionError(error)));
    renderDiagnosticResult({
      success: false,
      device_id: state.selectedDevice.device_id,
      management_ip: state.selectedDevice.management_ip,
      purpose: state.selectedPurpose,
      commands: state.latestPlan?.commands || [],
      error_summary: error.message,
      stdout: "",
      stderr: "",
      parsed_ports: [],
      interface_findings: {},
    });
    renderSummary(error.message, "error");
  } finally {
    nodes.collect.disabled = true;
    await loadAudit();
    await loadDashboard();
    await loadDiagnostics();
    await loadPorts();
  }
}

async function loadDashboard() {
  if (nodes.dashboardUpdated) {
    nodes.dashboardUpdated.textContent = "Loading topology and device health...";
  }
  nodes.healthCards?.replaceChildren();
  nodes.topologyMap?.replaceChildren();
  nodes.alarmFeed?.replaceChildren();

  const topology = await api("/topology");
  state.topologyEdges = Array.isArray(topology.edges) ? topology.edges : [];
  state.topologySummary = topology.summary || {};
  state.dashboardDevices = (topology.nodes || []).map((device) => ({
    device,
    findings: Array.isArray(device.findings) ? device.findings : [],
    severity: device.severity || "info",
    snapshotAvailable: !device.stale,
    snapshotMessage: device.stale ? "No live parsed snapshot yet." : "",
    loadError: "",
  }));
  renderDashboard();
}

function renderDashboard() {
  renderHealthCards();
  renderTopologyMap();
  renderAlarmFeed();
}

function renderHealthCards() {
  const rows = state.dashboardDevices;
  const counts = {
    critical: rows.filter((row) => row.severity === "critical").length,
    warning: rows.filter((row) => row.severity === "warning").length,
    stale: rows.filter((row) => !row.snapshotAvailable).length,
    collectable: rows.filter((row) => isCollectable(row.device)).length,
    total: rows.length,
  };
  const cards = [
    ["critical", "장애", counts.critical, "critical"],
    ["warning", "경고", counts.warning, "warning"],
    ["stale", "Stale", counts.stale, "stale"],
    ["collectable", "수집 가능", counts.collectable, "ok"],
    ["total", "전체 장비", counts.total, "neutral"],
  ];

  if (!nodes.healthCards) {
    const edgeCount = state.topologySummary.edges || state.topologyEdges.length;
    if (nodes.dashboardUpdated) {
      nodes.dashboardUpdated.textContent = `${counts.total} devices, ${edgeCount} links loaded. Click a node for diagnostics.`;
    }
    return;
  }

  nodes.healthCards.replaceChildren();
  for (const [filter, label, count, tone] of cards) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `health-card ${tone}`;
    button.dataset.filter = filter;
    const activeFilter = filter === "total" ? "all" : filter;
    button.setAttribute("aria-pressed", state.dashboardFilter === activeFilter ? "true" : "false");
    button.addEventListener("click", () => {
      state.dashboardFilter = filter === "total" ? "all" : filter;
      state.topologyAutoFit = false;
      state.topologyZoom = 1;
      renderDashboard();
    });

    const value = document.createElement("span");
    value.className = "health-card-value";
    value.textContent = String(count);

    const title = document.createElement("span");
    title.className = "health-card-label";
    title.textContent = label;

    button.append(value, title);
    nodes.healthCards.append(button);
  }
  const edgeCount = state.topologySummary.edges || state.topologyEdges.length;
  nodes.dashboardUpdated.textContent = `${counts.total} devices, ${edgeCount} links loaded. Click a node or link for drill-down.`;
}

function renderTopologyMap() {
  if (!nodes.topologyMap) {
    return;
  }
  const rows = filteredDashboardRows();
  nodes.topologyMap.replaceChildren();

  if (!rows.length) {
    const empty = document.createElement("div");
    empty.className = "dashboard-empty";
    empty.textContent = "No devices match this dashboard filter.";
    nodes.topologyMap.append(empty);
    updateTopologyMapStatus(0, 0);
    return;
  }

  const controls = createTopologyControls();
  const viewport = document.createElement("div");
  viewport.className = "topology-tree-viewport";
  const canvas = document.createElement("div");
  canvas.className = "topology-canvas topology-tree-canvas";
  canvas.style.setProperty("--topology-zoom", String(state.topologyZoom));
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.classList.add("topology-links");
  svg.setAttribute("aria-label", "Hierarchical network topology links");
  const nodeLayer = document.createElement("div");
  nodeLayer.className = "topology-node-layer";

  canvas.append(svg, nodeLayer);
  viewport.append(canvas);
  nodes.topologyMap.append(controls, viewport);
  requestAnimationFrame(() => renderTopologyTree(viewport, canvas, svg, nodeLayer, rows));
}

function createDeviceNode(row) {
  const button = document.createElement("button");
  const status = dashboardStatus(row);
  button.type = "button";
  button.className = `device-node ${status}`;
  button.dataset.nodeId = row.device.device_id;
  button.title = `${row.device.hostname || row.device.device_id} · ${dashboardStatusLabel(row)}`;
  button.addEventListener("click", () => openManagedDevice(row.device.device_id));
  if (state.selectedDevice?.device_id === row.device.device_id) {
    button.classList.add("selected");
  }

  const name = document.createElement("span");
  name.className = "device-node-name";
  name.textContent = row.device.hostname || row.device.device_id;

  const meta = document.createElement("span");
  meta.className = "device-node-meta";
  meta.textContent = `${topologyTierLabel(topologyTier(row))} · ${row.device.vendor} · ${row.device.role}`;

  const badge = severityBadge(dashboardStatus(row), dashboardStatusLabel(row));
  badge.classList.add("device-node-badge");

  const linkMeta = document.createElement("span");
  linkMeta.className = "device-node-links";
  linkMeta.textContent = linkSummary(row.device.device_id);

  button.append(name, meta, badge, linkMeta);
  return button;
}

function createTopologyControls() {
  const controls = document.createElement("div");
  controls.className = "topology-controls";

  const title = document.createElement("span");
  title.className = "topology-controls-title";
  title.textContent = "Tree layout";

  const stream = document.createElement("span");
  stream.className = `topology-stream-state ${state.topologyStreamStale ? "stale" : "live"}`;
  stream.textContent = state.topologyStreamStale ? "stream stale" : "stream ready";

  const floorFilter = topologySelectControl(
    "Floor",
    state.topologyFloorFilter,
    topologyFloorOptions(),
    (value) => {
      state.topologyFloorFilter = value;
      state.topologyAutoFit = false;
      state.topologyZoom = 1;
      renderTopologyMap();
    },
  );
  const vendorFilter = topologySelectControl(
    "Vendor",
    state.topologyVendorFilter,
    topologyVendorOptions(),
    (value) => {
      state.topologyVendorFilter = value;
      state.topologyAutoFit = false;
      state.topologyZoom = 1;
      renderTopologyMap();
    },
  );
  const tierFilter = topologySelectControl(
    "Tier",
    state.topologyTierFilter,
    topologyTierOptions(),
    (value) => {
      state.topologyTierFilter = value;
      state.topologyAutoFit = false;
      state.topologyZoom = 1;
      renderTopologyMap();
    },
  );

  const zoomOut = topologyControlButton("-", "Zoom out", () => {
    state.topologyAutoFit = false;
    state.topologyZoom = Math.max(0.5, Math.round((state.topologyZoom - 0.1) * 100) / 100);
    renderTopologyMap();
  });
  const zoomIn = topologyControlButton("+", "Zoom in", () => {
    state.topologyAutoFit = false;
    state.topologyZoom = Math.min(1.6, Math.round((state.topologyZoom + 0.1) * 100) / 100);
    renderTopologyMap();
  });
  const fit = topologyControlButton("Fit", "Fit topology to view", () => {
    state.topologyAutoFit = true;
    renderTopologyMap();
  });
  fit.setAttribute("aria-pressed", state.topologyAutoFit ? "true" : "false");

  controls.append(title, stream, floorFilter, vendorFilter, tierFilter, zoomOut, zoomIn, fit);
  return controls;
}

function topologySelectControl(labelText, value, options, onChange) {
  const label = document.createElement("label");
  label.className = "topology-filter";

  const span = document.createElement("span");
  span.textContent = labelText;

  const select = document.createElement("select");
  select.value = value;
  for (const option of options) {
    const item = document.createElement("option");
    item.value = option.value;
    item.textContent = option.label;
    select.append(item);
  }
  select.value = value;
  select.addEventListener("change", () => onChange(select.value));

  label.append(span, select);
  return label;
}

function topologyFloorOptions() {
  const floors = new Set();
  for (const row of state.dashboardDevices) {
    const floor = topologyFloor(row);
    if (floor) {
      floors.add(floor);
    }
  }
  return [
    { value: "all", label: "All floors" },
    ...Array.from(floors)
      .sort(compareFloors)
      .map((floor) => ({ value: floor, label: floor })),
  ];
}

function topologyVendorOptions() {
  const vendors = Array.from(new Set(state.dashboardDevices.map((row) => String(row.device.vendor || "").toLowerCase()).filter(Boolean)))
    .sort();
  return [
    { value: "all", label: "All vendors" },
    ...vendors.map((vendor) => ({ value: vendor, label: vendor.toUpperCase() })),
  ];
}

function topologyTierOptions() {
  return [
    { value: "all", label: "All tiers" },
    { value: "backbone", label: "Backbone" },
    { value: "distribution", label: "Distribution" },
    { value: "access", label: "Access" },
  ];
}

function topologyControlButton(label, title, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "topology-control-button";
  button.title = title;
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function renderTopologyTree(viewport, canvas, svg, nodeLayer, rows) {
  const layout = layoutTopologyRows(rows, topologyMaxColumns(viewport));
  const zoom = state.topologyAutoFit ? fitTopologyZoom(layout, viewport) : state.topologyZoom;
  state.topologyZoom = zoom;
  canvas.style.setProperty("--topology-zoom", String(zoom));
  canvas.style.width = `${layout.width}px`;
  canvas.style.height = `${layout.height}px`;
  canvas.style.minWidth = `${layout.width}px`;
  canvas.style.minHeight = `${layout.height}px`;
  if (state.topologyAutoFit) {
    viewport.scrollLeft = 0;
    viewport.scrollTop = 0;
  }
  nodeLayer.replaceChildren();

  for (const item of layout.nodes) {
    const node = createDeviceNode(item.row);
    node.classList.add("topology-tree-node");
    node.style.left = `${item.x}px`;
    node.style.top = `${item.y}px`;
    node.style.width = `${TOPOLOGY_LAYOUT.nodeWidth}px`;
    node.style.minHeight = `${TOPOLOGY_LAYOUT.nodeHeight}px`;
    node.style.borderColor = STATUS_COLOR[dashboardStatus(item.row)] || STATUS_COLOR.stale;
    nodeLayer.append(node);
  }

  renderTopologyLinks(svg, layout);
  updateTopologyMapStatus(layout.nodes.length, layout.edges.length);
}

function fitTopologyZoom(layout, viewport) {
  const availableWidth = Math.max(320, viewport.clientWidth - 18);
  const availableHeight = Math.max(260, viewport.clientHeight - 18);
  const widthZoom = availableWidth / Math.max(layout.width, 1);
  const heightZoom = availableHeight / Math.max(layout.height, 1);
  const zoom = Math.min(widthZoom, heightZoom, 1);
  return Math.max(0.28, Math.floor(zoom * 100) / 100);
}

function topologyMaxColumns(viewport) {
  const availableWidth = Math.max(360, viewport.clientWidth - TOPOLOGY_LAYOUT.paddingX * 2);
  const unitWidth = TOPOLOGY_LAYOUT.nodeWidth + TOPOLOGY_LAYOUT.nodeGap;
  const viewportColumns = Math.floor((availableWidth + TOPOLOGY_LAYOUT.nodeGap) / unitWidth);
  return Math.max(2, Math.min(10, viewportColumns || 10));
}

function layoutTopologyRows(rows, maxColumns = 7) {
  const tierOrder = ["backbone", "distribution", "access"];
  const grouped = new Map(tierOrder.map((tier) => [tier, []]));
  for (const row of rows) {
    grouped.get(topologyTier(row)).push(row);
  }
  for (const tier of tierOrder) {
    grouped.get(tier).sort(compareTopologyRows);
  }

  if (!grouped.get("distribution").length && grouped.get("backbone").length && grouped.get("access").length) {
    return layoutParentGroupedTopologyRows(grouped);
  }

  const activeTiers = tierOrder.filter((tier) => grouped.get(tier).length);
  const tierLayouts = activeTiers.map((tier) => topologyTierLayout(grouped.get(tier), maxColumns));
  const tierWidth = Math.max(1, ...tierLayouts.map((layout) => layout.width));
  const width = Math.max(1200, tierWidth + TOPOLOGY_LAYOUT.paddingX * 2);
  const height =
    TOPOLOGY_LAYOUT.paddingY * 2 +
    tierLayouts.reduce((total, layout) => total + layout.height, 0) +
    Math.max(0, activeTiers.length - 1) * TOPOLOGY_LAYOUT.tierGap;
  const nodesById = new Map();
  const positioned = [];
  let tierY = TOPOLOGY_LAYOUT.paddingY;

  activeTiers.forEach((tier, tierIndex) => {
    const tierRows = grouped.get(tier);
    const tierLayout = tierLayouts[tierIndex];
    tierRows.forEach((row, index) => {
      const tierRow = Math.floor(index / tierLayout.columns);
      const column = index % tierLayout.columns;
      const itemsInRow = Math.min(tierLayout.columns, tierRows.length - tierRow * tierLayout.columns);
      const rowWidth = itemsInRow * TOPOLOGY_LAYOUT.nodeWidth + Math.max(0, itemsInRow - 1) * TOPOLOGY_LAYOUT.nodeGap;
      const startX = (width - rowWidth) / 2;
      const node = {
        row,
        tier,
        rank: tierIndex,
        x: startX + column * (TOPOLOGY_LAYOUT.nodeWidth + TOPOLOGY_LAYOUT.nodeGap),
        y: tierY + tierRow * (TOPOLOGY_LAYOUT.nodeHeight + TOPOLOGY_LAYOUT.tierRowGap),
      };
      positioned.push(node);
      nodesById.set(row.device.device_id, node);
    });
    tierY += tierLayout.height + TOPOLOGY_LAYOUT.tierGap;
  });

  return {
    width,
    height,
    nodes: positioned,
    nodesById,
    edges: topologyVisibleEdges(nodesById),
  };
}

function layoutParentGroupedTopologyRows(grouped) {
  const backboneRows = grouped.get("backbone");
  const accessRows = grouped.get("access");
  const groupGap = 180;
  const accessGroups = topologyAccessGroups(accessRows);
  const groupColumns = accessGroups.length > 1 ? 2 : 3;
  const groupLayouts = accessGroups.map((group) => ({
    ...group,
    layout: topologyTierLayout(group.rows, groupColumns),
  }));
  const accessWidth =
    groupLayouts.reduce((total, group) => total + group.layout.width, 0) +
    Math.max(0, groupLayouts.length - 1) * groupGap;
  const width = Math.max(1320, accessWidth + TOPOLOGY_LAYOUT.paddingX * 2);
  const backboneY = TOPOLOGY_LAYOUT.paddingY;
  const accessY = backboneY + TOPOLOGY_LAYOUT.nodeHeight + TOPOLOGY_LAYOUT.tierGap;
  const height =
    accessY +
    Math.max(TOPOLOGY_LAYOUT.nodeHeight, ...groupLayouts.map((group) => group.layout.height)) +
    TOPOLOGY_LAYOUT.paddingY;
  const nodesById = new Map();
  const positioned = [];

  let groupX = (width - accessWidth) / 2;
  const groupCenters = new Map();
  for (const group of groupLayouts) {
    const center = groupX + group.layout.width / 2;
    groupCenters.set(group.parentId, center);
    positionTopologyGroup({
      rows: group.rows,
      columns: group.layout.columns,
      groupWidth: group.layout.width,
      startX: groupX,
      startY: accessY,
      tier: "access",
      rank: 1,
      positioned,
      nodesById,
    });
    groupX += group.layout.width + groupGap;
  }

  const orderedBackbones = backboneRows.slice().sort(compareTopologyRows);
  orderedBackbones.forEach((row, index) => {
    const fallbackX =
      (width - orderedBackbones.length * TOPOLOGY_LAYOUT.nodeWidth - Math.max(0, orderedBackbones.length - 1) * TOPOLOGY_LAYOUT.nodeGap) / 2 +
      index * (TOPOLOGY_LAYOUT.nodeWidth + TOPOLOGY_LAYOUT.nodeGap);
    const center = groupCenters.get(row.device.device_id);
    const x = center ? center - TOPOLOGY_LAYOUT.nodeWidth / 2 : fallbackX;
    const node = {
      row,
      tier: "backbone",
      rank: 0,
      x: Math.max(TOPOLOGY_LAYOUT.paddingX, Math.min(width - TOPOLOGY_LAYOUT.paddingX - TOPOLOGY_LAYOUT.nodeWidth, x)),
      y: backboneY,
    };
    positioned.push(node);
    nodesById.set(row.device.device_id, node);
  });

  return {
    width,
    height,
    nodes: positioned,
    nodesById,
    edges: topologyVisibleEdges(nodesById),
  };
}

function topologyAccessGroups(rows) {
  const groups = new Map();
  for (const row of rows) {
    const parentId = topologyPrimaryParent(row.device.device_id) || `vendor-${String(row.device.vendor || "other").toLowerCase()}`;
    if (!groups.has(parentId)) {
      groups.set(parentId, []);
    }
    groups.get(parentId).push(row);
  }
  return Array.from(groups.entries())
    .map(([parentId, groupRows]) => ({
      parentId,
      rows: groupRows.slice().sort(compareTopologyRows),
    }))
    .sort((left, right) => topologyParentSortRank(left.parentId).localeCompare(topologyParentSortRank(right.parentId)));
}

function positionTopologyGroup({ rows, columns, groupWidth, startX, startY, tier, rank, positioned, nodesById }) {
  rows.forEach((row, index) => {
    const tierRow = Math.floor(index / columns);
    const column = index % columns;
    const itemsInRow = Math.min(columns, rows.length - tierRow * columns);
    const rowWidth = itemsInRow * TOPOLOGY_LAYOUT.nodeWidth + Math.max(0, itemsInRow - 1) * TOPOLOGY_LAYOUT.nodeGap;
    const rowStartX = startX + (groupWidth - rowWidth) / 2;
    const node = {
      row,
      tier,
      rank,
      x: rowStartX + column * (TOPOLOGY_LAYOUT.nodeWidth + TOPOLOGY_LAYOUT.nodeGap),
      y: startY + tierRow * (TOPOLOGY_LAYOUT.nodeHeight + TOPOLOGY_LAYOUT.tierRowGap),
    };
    positioned.push(node);
    nodesById.set(row.device.device_id, node);
  });
}

function topologyTierLayout(rows, maxColumns) {
  const columns = Math.max(1, Math.min(maxColumns, rows.length || 1));
  const rowCount = Math.max(1, Math.ceil((rows.length || 1) / columns));
  return {
    columns,
    width: columns * TOPOLOGY_LAYOUT.nodeWidth + Math.max(0, columns - 1) * TOPOLOGY_LAYOUT.nodeGap,
    height: rowCount * TOPOLOGY_LAYOUT.nodeHeight + Math.max(0, rowCount - 1) * TOPOLOGY_LAYOUT.tierRowGap,
  };
}

function updateTopologyMapStatus(visibleDevices, visibleEdges) {
  if (!nodes.dashboardUpdated) {
    return;
  }
  const totalDevices = state.dashboardDevices.length;
  const totalEdges = state.topologySummary.edges || state.topologyEdges.length;
  const filters = activeTopologyFilterLabels();
  const suffix = page === "dashboard" ? "Click a node for diagnostics." : "Click a node or link for drill-down.";
  const filterText = filters.length ? ` Filter: ${filters.join(", ")}.` : "";
  nodes.dashboardUpdated.textContent = `${visibleDevices}/${totalDevices} devices, ${visibleEdges}/${totalEdges} links shown.${filterText} ${suffix}`;
}

function activeTopologyFilterLabels() {
  const labels = [];
  if (state.dashboardFilter !== "all") {
    labels.push(state.dashboardFilter === "issues" ? "issues" : state.dashboardFilter);
  }
  if (state.topologyFloorFilter !== "all") {
    labels.push(state.topologyFloorFilter);
  }
  if (state.topologyVendorFilter !== "all") {
    labels.push(state.topologyVendorFilter.toUpperCase());
  }
  if (state.topologyTierFilter !== "all") {
    labels.push(topologyTierLabel(state.topologyTierFilter));
  }
  return labels;
}

function topologyVisibleEdges(nodesById) {
  return state.topologyEdges
    .filter((edge) => edge.source_device_id && edge.target_device_id)
    .filter((edge) => nodesById.has(edge.source_device_id) && nodesById.has(edge.target_device_id));
}

function renderTopologyLinks(svg, layout) {
  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
  svg.setAttribute("width", String(layout.width));
  svg.setAttribute("height", String(layout.height));

  for (const edge of layout.edges) {
    const endpoints = topologyEdgeEndpoints(edge, layout.nodesById);
    if (!endpoints) {
      continue;
    }
    const { source, target } = endpoints;
    const geometry = topologyEdgeGeometry(source, target);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const health = topologyEdgeHealth(edge);
    path.classList.add("topology-link", edge.source_type === "live" ? "live" : "reference", `health-${health}`);
    if (edge.link_type === "port-channel") {
      path.classList.add("port-channel");
    }
    if (topologyEdgeIsStale(edge)) {
      path.classList.add("stale");
    }
    path.setAttribute("d", geometry.path);
    path.style.stroke = topologyEdgeColor(edge);
    path.style.strokeWidth = String(topologyEdgeWidth(edge));
    path.setAttribute("tabindex", "0");
    path.setAttribute("role", "link");
    path.setAttribute("aria-label", topologyEdgeLabel(edge));
    path.addEventListener("click", () => openTopologyEdge(edge));
    path.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openTopologyEdge(edge);
      }
    });

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = topologyEdgeLabel(edge);
    path.append(title);
    svg.append(path);
  }
}

function compareTopologyRows(left, right) {
  return topologySortKey(left).localeCompare(topologySortKey(right));
}

function topologySortKey(row) {
  const deviceId = String(row.device.device_id || "");
  if (deviceId === "cisco-backbone") {
    return "00-cisco-main";
  }
  if (deviceId === "arista-10g-core") {
    return "01-arista-10g";
  }
  const parent = topologyPrimaryParent(deviceId);
  const floor = topologyFloor(row);
  return `${topologyParentSortRank(parent)}-${floorRank(floor)}-${String(row.device.hostname || deviceId)}`;
}

function topologyPrimaryParent(deviceId) {
  const incoming = state.topologyEdges.find((edge) => edge.target_device_id === deviceId && edge.source_device_id);
  return incoming?.source_device_id || "";
}

function topologyParentSortRank(parentId) {
  if (parentId === "cisco-backbone") {
    return "00-cisco";
  }
  if (parentId === "arista-10g-core") {
    return "01-arista";
  }
  if (parentId === "vendor-cisco") {
    return "02-cisco-unlinked";
  }
  if (parentId === "vendor-arista") {
    return "03-arista-unlinked";
  }
  return "09-other";
}

function topologyEdgeEndpoints(edge, nodesById) {
  const source = nodesById.get(edge.source_device_id);
  const target = nodesById.get(edge.target_device_id);
  if (!source || !target) {
    return null;
  }
  if (source.rank > target.rank) {
    return { source: target, target: source };
  }
  return { source, target };
}

function topologyEdgeGeometry(source, target) {
  if (source.rank === target.rank) {
    const sourceBeforeTarget = source.x <= target.x;
    const x1 = sourceBeforeTarget ? source.x + TOPOLOGY_LAYOUT.nodeWidth : source.x;
    const x2 = sourceBeforeTarget ? target.x : target.x + TOPOLOGY_LAYOUT.nodeWidth;
    const y1 = source.y + TOPOLOGY_LAYOUT.nodeHeight / 2;
    const y2 = target.y + TOPOLOGY_LAYOUT.nodeHeight / 2;
    const curve = Math.max(Math.abs(x2 - x1) * 0.35, 42);
    const c1 = sourceBeforeTarget ? x1 + curve : x1 - curve;
    const c2 = sourceBeforeTarget ? x2 - curve : x2 + curve;
    return {
      path: `M ${x1} ${y1} C ${c1} ${y1}, ${c2} ${y2}, ${x2} ${y2}`,
      labelX: (x1 + x2) / 2,
      labelY: y1 - 12,
    };
  }

  const x1 = source.x + TOPOLOGY_LAYOUT.nodeWidth / 2;
  const y1 = source.y + TOPOLOGY_LAYOUT.nodeHeight;
  const x2 = target.x + TOPOLOGY_LAYOUT.nodeWidth / 2;
  const y2 = target.y;
  const curve = Math.max(Math.abs(y2 - y1) * 0.45, 34);
  return {
    path: `M ${x1} ${y1} C ${x1} ${y1 + curve}, ${x2} ${y2 - curve}, ${x2} ${y2}`,
    labelX: (x1 + x2) / 2,
    labelY: (y1 + y2) / 2,
  };
}

function topologyTier(row) {
  const role = String(row.device.role || "").toLowerCase();
  const hostname = String(row.device.hostname || "").toLowerCase();
  if (role.includes("backbone") || role.includes("core") || hostname.includes("backbone")) {
    return "backbone";
  }
  if (role.includes("aggregation") || role.includes("distribution") || role.includes("dist")) {
    return "distribution";
  }
  return "access";
}

function topologyFloor(row) {
  const values = [
    row.device.hostname,
    row.device.device_id,
    row.device.notes,
    row.device.management_ip,
  ].map((value) => String(value || "").toUpperCase());
  for (const value of values) {
    const match = value.match(/\b(B\d+F|\d+F)\b/);
    if (match) {
      return match[1];
    }
  }
  return "";
}

function compareFloors(left, right) {
  return floorRank(left) - floorRank(right) || left.localeCompare(right);
}

function floorRank(floor) {
  const basement = String(floor).match(/^B(\d+)F$/i);
  if (basement) {
    return -Number(basement[1]);
  }
  const above = String(floor).match(/^(\d+)F$/i);
  if (above) {
    return Number(above[1]);
  }
  return 999;
}

function topologyTierLabel(tier) {
  return {
    backbone: "Backbone/Core",
    distribution: "L3 Distribution",
    access: "L2 Access",
  }[tier] || "Access";
}

function topologyEdgeHealth(edge) {
  const memberStatuses = (Array.isArray(edge.members) ? edge.members : [])
    .map((member) => String(member.status || "").toLowerCase())
    .filter(Boolean);
  if (state.topologyStreamStale || memberStatuses.some((status) => ["down", "disabled", "errdisabled"].includes(status))) {
    return "fault";
  }
  if (!edge.target_device_id || String(edge.status || "").includes("unmanaged")) {
    return "warning";
  }
  if (topologyEdgeIsStale(edge)) {
    return "unreachable";
  }
  return "normal";
}

function topologyEdgeColor(edge) {
  return STATUS_COLOR[topologyEdgeHealth(edge)] || STATUS_COLOR.unreachable;
}

function topologyEdgeWidth(edge) {
  const utilization = Number(edge.metrics?.utilizationPct ?? edge.metrics?.utilization_pct ?? 0);
  const clamped = Number.isFinite(utilization) ? Math.max(0, Math.min(100, utilization)) : 0;
  const base = 2 + (clamped / 100) * 3;
  if (edge.link_type === "port-channel" || (Array.isArray(edge.members) && edge.members.length > 1)) {
    return Math.max(base, 4);
  }
  return base;
}

function topologyEdgeIsStale(edge) {
  return state.topologyStreamStale || edge.source_type !== "live" || String(edge.status || "").includes("stale");
}

function topologyEdgeLabel(edge) {
  return `${edge.source_device_id} ${edge.local_interface || ""} -> ${edge.target_device_id || edge.target_label || "unknown"} ${edge.remote_interface || ""} (${topologyEdgeHealth(edge)}, ${edge.source_type || "unknown"})`;
}

async function openTopologyEdge(edge) {
  if (!edge.source_device_id) {
    return;
  }
  await openManagedDevice(edge.source_device_id);
  const interfaceName = String(edge.local_interface || "").split(",")[0].trim();
  if (interfaceName) {
    await loadPortDetail(edge.source_device_id, interfaceName);
    document.querySelector(".detail-panel")?.scrollIntoView({ block: "start", behavior: "smooth" });
  }
}

function renderAlarmFeed() {
  if (!nodes.alarmFeed) {
    return;
  }
  const events = [];
  for (const row of state.dashboardDevices) {
    if (row.loadError) {
      events.push({
        severity: "critical",
        deviceId: row.device.device_id,
        title: "Dashboard data load failed",
        detail: row.loadError,
      });
    }
    for (const finding of row.findings) {
      if (["warning", "critical"].includes(finding.severity)) {
        events.push({
          severity: finding.severity,
          deviceId: row.device.device_id,
          interface: finding.interface,
          title: finding.title,
          detail: finding.evidence,
        });
      }
    }
    if (!row.snapshotAvailable) {
      events.push({
        severity: "stale",
        deviceId: row.device.device_id,
        title: "No live snapshot",
        detail: row.snapshotMessage || "Run CHECK or Collect to create a current parsed snapshot.",
      });
    }
  }

  for (const edge of state.topologyEdges) {
    if (!edge.target_device_id && edge.status !== "reference-managed") {
      events.push({
        severity: edge.status === "ip-not-set" ? "warning" : "stale",
        deviceId: edge.source_device_id,
        interface: edge.local_interface,
        title: "Unmanaged topology neighbor",
        detail: `${edge.target_label || "unknown"} via ${edge.local_interface || "-"} (${edge.status || edge.source_type})`,
      });
    }
  }

  events.sort((left, right) => severityRank(right.severity) - severityRank(left.severity));
  nodes.alarmFeed.replaceChildren();
  if (!events.length) {
    const empty = document.createElement("div");
    empty.className = "dashboard-empty";
    empty.textContent = "No actionable findings in the current snapshot.";
    nodes.alarmFeed.append(empty);
    return;
  }

  for (const event of events.slice(0, 30)) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `alarm-item ${event.severity}`;
    item.addEventListener("click", async () => {
      await openManagedDevice(event.deviceId);
      if (event.interface) {
        await loadPortDetail(event.deviceId, event.interface);
      }
    });

    const title = document.createElement("span");
    title.className = "alarm-title";
    title.textContent = event.interface ? `${event.deviceId} ${shortInterfaceName(event.interface)}` : event.deviceId;

    const detail = document.createElement("span");
    detail.className = "alarm-detail";
    detail.textContent = `${event.title}: ${event.detail}`;

    const badge = severityBadge(event.severity);
    badge.classList.add("alarm-badge");

    item.append(title, detail, badge);
    nodes.alarmFeed.append(item);
  }
}

function filteredDashboardRows() {
  const filter = state.dashboardFilter;
  let rows = state.dashboardDevices;
  if (filter === "all") {
    rows = state.dashboardDevices;
  } else if (filter === "critical" || filter === "warning") {
    rows = state.dashboardDevices.filter((row) => row.severity === filter);
  } else if (filter === "stale") {
    rows = state.dashboardDevices.filter((row) => !row.snapshotAvailable);
  } else if (filter === "collectable") {
    rows = state.dashboardDevices.filter((row) => isCollectable(row.device));
  } else {
    rows = state.dashboardDevices.filter((row) => dashboardStatus(row) !== "ok");
  }
  return rows.filter(matchesTopologyFilters);
}

function matchesTopologyFilters(row) {
  const vendor = String(row.device.vendor || "").toLowerCase();
  if (state.topologyVendorFilter !== "all" && vendor !== state.topologyVendorFilter) {
    return false;
  }

  const tier = topologyTier(row);
  if (state.topologyTierFilter !== "all" && tier !== state.topologyTierFilter) {
    return false;
  }

  if (state.topologyFloorFilter === "all") {
    return true;
  }

  return topologyFloor(row) === state.topologyFloorFilter || (state.topologyTierFilter === "all" && tier === "backbone");
}

function dashboardStatus(row) {
  if (row.loadError) {
    return "critical";
  }
  if (row.severity === "critical" || row.severity === "warning") {
    return row.severity;
  }
  if (!row.snapshotAvailable) {
    return "stale";
  }
  return "ok";
}

function dashboardStatusLabel(row) {
  const status = dashboardStatus(row);
  if (status === "ok") {
    return "normal";
  }
  if (status === "stale") {
    return "Unknown";
  }
  return SEVERITY[normalizeSeverity(status)]?.label || status;
}

function severityRank(severity) {
  return SEVERITY[normalizeSeverity(severity)]?.rank || 0;
}

function linkSummary(deviceId) {
  const outgoing = state.topologyEdges.filter((edge) => edge.source_device_id === deviceId).length;
  const incoming = state.topologyEdges.filter((edge) => edge.target_device_id === deviceId).length;
  if (!outgoing && !incoming) {
    return "links: none";
  }
  return `links: ${outgoing} out / ${incoming} in`;
}

function linkLabel(edge) {
  const local = String(edge.local_interface || "").split(",")[0].trim();
  const remote = String(edge.remote_interface || "").split(",")[0].trim();
  if (local && remote) {
    return `${local} -> ${remote}`;
  }
  return local || remote || edge.source_type || "link";
}

function cssEscape(value) {
  if (window.CSS?.escape) {
    return CSS.escape(value);
  }
  return String(value).replace(/["\\]/g, "\\$&");
}

function startTopologyStream() {
  if (state.topologyStreamStarted || !window.EventSource) {
    return;
  }
  state.topologyStreamStarted = true;
  const events = new EventSource("/events/monitoring");
  events.onopen = () => {
    state.topologyStreamStale = false;
    if (state.dashboardDevices.length) {
      renderDashboard();
    }
  };
  events.onmessage = (event) => {
    try {
      applyTopologyMonitoringPatch(JSON.parse(event.data));
    } catch {
      // Drop malformed stream frames; the next valid frame will refresh state.
    }
  };
  events.onerror = () => {
    state.topologyStreamStale = true;
    if (state.dashboardDevices.length) {
      renderDashboard();
    }
  };
}

function applyTopologyMonitoringPatch(payload) {
  if (!payload?.available || !payload.device_id) {
    return;
  }
  const row = state.dashboardDevices.find((item) => item.device.device_id === payload.device_id);
  if (!row) {
    return;
  }
  row.snapshotAvailable = Boolean(payload.success);
  row.snapshotMessage = payload.success ? "" : "Latest server-side collection failed.";
  if (payload.success === false) {
    row.severity = "critical";
    row.findings = [
      {
        severity: "critical",
        title: "Collection failed",
        evidence: "Latest server-side collection event reported failure.",
      },
      ...row.findings,
    ];
  }
  for (const edge of state.topologyEdges) {
    if (edge.source_device_id === payload.device_id || edge.target_device_id === payload.device_id) {
      edge.metrics = { ...(edge.metrics || {}), stale: !payload.success };
    }
  }
  state.topologyStreamStale = false;
  renderDashboard();
}

function setCollectionResultText(value) {
  if (!nodes.collectionResult) {
    return;
  }
  nodes.collectionResult.textContent = value;
}

function setCollectionResultHtml(value) {
  if (!nodes.collectionResult) {
    return;
  }
  nodes.collectionResult.innerHTML = value;
}

function renderDiagnosticResult(result) {
  state.latestResult = result;
  if (!result) {
    state.rawOutput = "";
    nodes.collectionSummary && (nodes.collectionSummary.innerHTML = '<div class="empty-state">No diagnostic result yet. Preview and run a read-only diagnostic to populate the parsed summary.</div>');
    nodes.collectionMetrics && (nodes.collectionMetrics.innerHTML = '<div class="empty-state">No parsed metrics yet.</div>');
    setCollectionResultText("No raw CLI output yet.");
    if (nodes.resultMeta) {
      nodes.resultMeta.textContent = "Parsed summary is shown before raw CLI output.";
    }
    return;
  }

  const deviceId = result.device?.device_id || result.device_id || state.selectedDevice?.device_id || "-";
  const managementIp = result.device?.management_ip || result.management_ip || state.selectedDevice?.management_ip || "-";
  const status = result.success ? resultSeverity(result) : "critical";
  if (nodes.resultMeta) {
    nodes.resultMeta.textContent = `${deviceId} (${managementIp}) - ${text(result.purpose)} - ${result.success ? "success" : "failure"}`;
  }
  renderResultSummary(result, status);
  renderResultMetrics(result);
  state.rawOutput = rawOutputFromResult(result);
  renderRawOutput();
  activateResultTab("summary");
}

function renderResultSummary(result, status) {
  if (!nodes.collectionSummary) {
    return;
  }
  nodes.collectionSummary.replaceChildren();
  const header = document.createElement("div");
  header.className = "result-summary-head";
  header.append(severityBadge(status));
  const title = document.createElement("strong");
  title.textContent = result.success ? "Parsed Summary" : "Execution Failed";
  header.prepend(title);

  const list = document.createElement("ul");
  list.className = "summary-list";
  const findings = parsedSummaryLines(result);
  for (const line of findings) {
    const item = document.createElement("li");
    item.textContent = line;
    list.append(item);
  }
  nodes.collectionSummary.append(header, list);
}

function parsedSummaryLines(result) {
  if (!result.success) {
    return [
      `Final result status: failure`,
      `Key abnormal finding: ${text(result.error_summary || "Read-only command execution failed.")}`,
      "Recommended next check: verify reachability, authentication, and collector support before retrying.",
      `Related device: ${text(result.device?.device_id || result.device_id || state.selectedDevice?.device_id)}`,
      `Execution time: ${new Date().toLocaleString()}`,
      "Executed by: current web session",
    ];
  }
  const ports = Array.isArray(result.parsed_ports) ? result.parsed_ports : [];
  const findings = result.interface_findings || {};
  const highErrors = Array.isArray(findings.high_error_ports) ? findings.high_error_ports : [];
  const lowSpeed = Array.isArray(findings.low_speed_connected_ports) ? findings.low_speed_connected_ports : [];
  const disabled = Array.isArray(findings.disabled_ports) ? findings.disabled_ports : [];
  const selected = state.selectedPort;
  const lines = [
    "Final result status: read-only collection succeeded.",
    highErrors.length
      ? `Key abnormal findings: ${highErrors.length} high-error port(s), including ${highErrors[0].interface}.`
      : "Key abnormal findings: no high-error ports in parsed output.",
    lowSpeed.length
      ? `Low-speed findings: ${lowSpeed.length} connected port(s) below expected speed.`
      : "Normal findings: no low-speed connected ports found.",
    disabled.length
      ? `Disabled ports: ${disabled.length} disabled or errdisabled port(s).`
      : "Disabled ports: no disabled/errdisabled ports reported in parsed output.",
    `Related port: ${selected?.interface || "device scope"}`,
    `Related VLAN: ${selected?.vlan || "not selected"}`,
    `Related MAC address: ${listText(selected?.endpoint_macs)}`,
    highErrors.length
      ? "Recommended next check: inspect cable, endpoint NIC, and switchport counters."
      : "Recommended next check: review Raw CLI only if technical evidence is needed.",
    `Parsed ports: ${ports.length}`,
    `Executed by: current web session`,
  ];
  return lines;
}

function renderResultMetrics(result) {
  if (!nodes.collectionMetrics) {
    return;
  }
  nodes.collectionMetrics.replaceChildren();
  const ports = Array.isArray(result.parsed_ports) ? result.parsed_ports : [];
  const findings = result.interface_findings || {};
  const metrics = [
    ["Commands", Array.isArray(result.commands) ? result.commands.length : 0],
    ["Parsed Ports", ports.length],
    ["High Error Ports", Array.isArray(findings.high_error_ports) ? findings.high_error_ports.length : 0],
    ["Low Speed Ports", Array.isArray(findings.low_speed_connected_ports) ? findings.low_speed_connected_ports.length : 0],
    ["Disabled Ports", Array.isArray(findings.disabled_ports) ? findings.disabled_ports.length : 0],
    ["Stdout Bytes", result.stdout_bytes || String(result.stdout || "").length],
    ["Stderr Bytes", result.stderr_bytes || String(result.stderr || "").length],
  ];
  const strip = document.createElement("div");
  strip.className = "metric-strip result-metrics";
  for (const [label, value] of metrics) {
    const item = document.createElement("div");
    item.className = "metric-card";
    const strong = document.createElement("strong");
    strong.textContent = text(value);
    const span = document.createElement("span");
    span.textContent = label;
    item.append(strong, span);
    strip.append(item);
  }
  nodes.collectionMetrics.append(strip);
}

function rawOutputFromResult(result) {
  const lines = [
    `Device : ${result.device?.device_id || result.device_id || state.selectedDevice?.device_id || "-"}`,
    `IP     : ${result.device?.management_ip || result.management_ip || state.selectedDevice?.management_ip || "-"}`,
    `Purpose: ${text(result.purpose)}`,
    `Status : ${result.success ? "Success" : "Failure"}`,
    `Commands: ${Array.isArray(result.commands) ? result.commands.join(" | ") : "-"}`,
    "",
    "------------------------------------------------------------",
    result.stdout || "(no stdout)",
  ];
  if (result.stderr) {
    lines.push("", "===== STDERR =====", result.stderr);
  }
  if (result.error_summary) {
    lines.push("", "===== ERROR SUMMARY =====", result.error_summary);
  }
  return lines.join("\n");
}

function renderRawOutput() {
  if (!nodes.collectionResult) {
    return;
  }
  const query = state.rawSearchQuery;
  const raw = state.rawOutput || "No raw CLI output yet.";
  if (!query) {
    nodes.collectionResult.innerHTML = colorizeStatusTokens(escapeHtml(raw));
    return;
  }
  const escaped = escapeHtml(raw);
  const pattern = new RegExp(`(${escapeRegExp(query)})`, "gi");
  nodes.collectionResult.innerHTML = colorizeStatusTokens(escaped.replace(pattern, '<mark>$1</mark>'));
}

function resultSeverity(result) {
  const findings = result.interface_findings || {};
  if (Array.isArray(findings.high_error_ports) && findings.high_error_ports.length) {
    return "critical";
  }
  if (Array.isArray(findings.low_speed_connected_ports) && findings.low_speed_connected_ports.length) {
    return "warning";
  }
  if (Array.isArray(findings.disabled_ports) && findings.disabled_ports.length) {
    return "warning";
  }
  return "normal";
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function formatCollectionResultHtml(result) {
  const endpointSummary = formatEndpointIpSummary(result);
  const interfaceSummary = formatInterfaceFindingSummary(result);
  const portEndpointTrace = formatPortEndpointTrace(result.port_endpoint_trace);
  const lines = [
    `Device: ${result.device_id} (${result.management_ip})`,
    `Purpose: ${result.purpose}`,
    `Result: ${result.success ? "success" : "failure"}    returncode=${text(result.returncode)}    stdout=${text(result.stdout_bytes)} bytes    stderr=${text(result.stderr_bytes)} bytes`,
    `Commands: ${Array.isArray(result.commands) ? result.commands.join(" | ") : "-"}`,
  ];

  if (portEndpointTrace) {
    lines.push("", "===== PORT ENDPOINT TRACE =====", portEndpointTrace);
  }

  if (endpointSummary) {
    lines.push("", "===== CONNECTED ENDPOINTS =====", endpointSummary);
  }

  if (interfaceSummary) {
    lines.push("", "===== INTERFACE FINDINGS =====", interfaceSummary);
  }

  lines.push(
    "",
    "===== STDOUT =====",
    result.stdout || "(no stdout)",
  );

  if (!result.success && result.stderr) {
    lines.push("", "===== STDERR =====", result.stderr);
  }

  if (result.error_summary) {
    lines.push("", "===== ERROR SUMMARY =====", result.error_summary);
  }

  return colorizeStatusTokens(escapeHtml(lines.join("\n")));
}

function formatPortEndpointTrace(trace) {
  if (!Array.isArray(trace) || !trace.length) {
    return "";
  }

  const lines = [];
  for (const row of trace) {
    const endpoints = Array.isArray(row.endpoints) ? row.endpoints : [];
    if (!endpoints.length) {
      continue;
    }
    lines.push(`${row.interface || "-"}  ${row.status || "-"}/${row.speed || "-"}  vlan=${row.vlan || "-"}  ${row.description || "-"}`);
    for (const endpoint of endpoints) {
      const ips = Array.isArray(endpoint.ips) && endpoint.ips.length ? endpoint.ips.join(", ") : "-";
      lines.push(`  - ip=${ips.padEnd(15)} mac=${endpoint.mac || "-"}`);
    }
  }
  return lines.join("\n");
}

function formatCheckResultHtml(result) {
  const device = result.device || {};
  const lines = [
    `Device: ${device.device_id || "-"} (${device.management_ip || "-"})`,
    "Purpose: check",
    `Result: ${result.success ? "success" : "failure"}    returncode=${text(result.returncode)}    stdout=${text(result.stdout_bytes)} bytes    stderr=${text(result.stderr_bytes)} bytes`,
    `Purposes: ${Array.isArray(result.purposes_collected) ? result.purposes_collected.join(" | ") : "-"}`,
    `Commands: ${Array.isArray(result.commands) ? result.commands.join(" | ") : "-"}`,
    "",
    "===== NETWORK CHECK =====",
  ];

  for (const item of result.check_items || []) {
    const status = String(item.status || "unknown").replaceAll("_", " ").toUpperCase();
    lines.push(`[${status}] ${item.label}: ${item.detail}`);
  }

  const interfaceSummary = formatInterfaceFindingSummary(result);
  if (interfaceSummary) {
    lines.push("", "===== INTERFACE FINDINGS =====", interfaceSummary);
  }

  if (Array.isArray(result.parsed_ports) && result.parsed_ports.length) {
    const endpoints = formatEndpointIpSummaryFromPorts(result.parsed_ports);
    if (endpoints) {
      lines.push("", "===== CONNECTED ENDPOINTS =====", endpoints);
    }
  }

  lines.push("", "===== STDOUT =====", result.stdout || "(no stdout)");

  if (!result.success && result.stderr) {
    lines.push("", "===== STDERR =====", result.stderr);
  }

  if (result.error_summary) {
    lines.push("", "===== ERROR SUMMARY =====", result.error_summary);
  }

  return colorizeStatusTokens(escapeHtml(lines.join("\n")));
}

function formatInterfaceFindingSummary(result) {
  const findings = result.interface_findings || {};
  const lowSpeedRows = Array.isArray(findings.low_speed_connected_ports) ? findings.low_speed_connected_ports : [];
  const disabledRows = Array.isArray(findings.disabled_ports) ? findings.disabled_ports : [];
  const highCounterRows = Array.isArray(findings.high_error_ports) ? findings.high_error_ports : [];
  if (!lowSpeedRows.length && !disabledRows.length && !highCounterRows.length) {
    return "";
  }

  const lines = [];
  lines.push("LOW-SPEED CONNECTED PORTS");
  if (lowSpeedRows.length) {
    for (const port of lowSpeedRows) {
      lines.push(`- ${port.interface}  status=${port.status}  vlan=${port.vlan || "-"}  duplex=${port.duplex || "-"}  speed=${port.speed || "-"}`);
    }
  } else {
    lines.push("- none found in collected interface status");
  }

  if (disabledRows.length) {
    lines.push("", "DISABLED PORTS");
    for (const port of disabledRows) {
      lines.push(`- ${port.interface}  status=${port.status}  vlan=${port.vlan || "-"}  speed=${port.speed || "-"}`);
    }
  }

  if (highCounterRows.length) {
    lines.push("", "HIGH ERROR COUNTERS");
    for (const port of highCounterRows) {
      lines.push(`- ${port.interface}  current=${port.status || "-"}/${port.speed || "-"}  FCS=${port.fcs_errors || 0}  Rx=${port.rx_errors || 0}  Runts=${port.runts || 0}  Tx=${port.tx_errors || 0}`);
    }
  }

  return lines.join("\n");
}

function formatEndpointIpSummary(result) {
  if (Array.isArray(result.parsed_ports) && result.parsed_ports.length) {
    return formatEndpointIpSummaryFromPorts(result.parsed_ports);
  }
  return "";
}

function formatEndpointIpSummaryFromPorts(ports) {
  const lines = [];
  for (const port of ports) {
    const endpoints = [];
    for (const ip of port.endpoint_ips || []) {
      endpoints.push({ ip, mac: "-" });
    }
    for (const mac of port.endpoint_macs || []) {
      if (!endpoints.some((endpoint) => endpoint.mac === mac)) {
        endpoints.push({ ip: "-", mac });
      }
    }
    if (!endpoints.length) {
      continue;
    }
    lines.push(`${port.interface}  ${port.status || "-"}/${port.speed || "-"}  ${port.description || "-"}`);
    for (const endpoint of endpoints) {
      lines.push(`  - ip=${String(endpoint.ip).padEnd(15)} mac=${endpoint.mac}`);
    }
  }
  return lines.join("\n");
}

function formatCollectionError(error) {
  return [
    `Device: ${state.selectedDevice?.device_id || "-"}`,
    `Purpose: ${state.selectedPurpose || "-"}`,
    "Result: failure",
    "",
    "===== ERROR SUMMARY =====",
    error.message,
  ].join("\n");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function colorizeStatusTokens(value) {
  return value
    .replace(/\bconnected\b/g, '<span class="status-connected">connected</span>')
    .replace(/\bdisabled\b/g, '<span class="status-disabled">disabled</span>');
}

function summaryFromResult(result) {
  if (result.success) {
    return `Collection succeeded. returncode=${result.returncode}, stdout_bytes=${result.stdout_bytes}, stderr_bytes=${result.stderr_bytes}.`;
  }
  return `Collection failed. returncode=${text(result.returncode)}. ${text(result.error_summary)}`;
}

function renderSummary(message, className) {
  if (!nodes.diagnosticSummary) {
    return;
  }
  nodes.diagnosticSummary.className = `summary-box ${className}`;
  nodes.diagnosticSummary.textContent = message;
}

async function loadDiagnostics() {
  if (!nodes.diagnosticFindings) {
    return;
  }
  nodes.diagnosticFindings.replaceChildren();
  if (!state.selectedDevice) {
    renderSummary("Select a device.", "warn");
    return;
  }

  const payload = await api(`/devices/${encodeURIComponent(state.selectedDevice.device_id)}/diagnostics`);
  const severity = highestSeverity(payload.findings);
  renderSummary(payload.summary, severityClass(severity));
  for (const finding of payload.findings) {
    const item = document.createElement("article");
    item.className = `finding ${finding.severity}`;

    const title = document.createElement("div");
    title.className = "finding-title";
    const titleText = document.createElement("span");
    titleText.textContent = finding.interface ? `${finding.interface}: ${finding.title}` : finding.title;
    const badge = severityBadge(finding.severity);
    badge.classList.add("finding-severity");
    title.append(titleText, badge);

    const evidence = document.createElement("p");
    evidence.textContent = finding.evidence;
    const next = document.createElement("p");
    next.textContent = `Next: ${finding.next_step}`;
    item.append(title, evidence, next);
    nodes.diagnosticFindings.append(item);
  }
}

async function loadNeighbors() {
  if (!nodes.neighborsBody || !nodes.neighborsNote) {
    return;
  }
  nodes.neighborsBody.replaceChildren();
  nodes.neighborsNote.textContent = "Reference only";
  if (!state.selectedDevice) {
    return;
  }

  const payload = await api(`/devices/${encodeURIComponent(state.selectedDevice.device_id)}/neighbors`);
  nodes.neighborsNote.textContent = payload.reference_note;
  if (!payload.neighbors.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 9;
    cell.className = "muted empty-cell";
    cell.textContent = "No backbone neighbor reference for this device.";
    row.append(cell);
    nodes.neighborsBody.append(row);
    return;
  }

  for (const neighbor of payload.neighbors) {
    const row = document.createElement("tr");
    const managedDevice = findManagedNeighbor(neighbor);
    appendNeighborAction(row, managedDevice);
    appendCells(row, [
      shortInterfaceName(neighbor.local_interface),
      neighbor.neighbor_name,
      neighbor.management_ip || "IP not set",
      neighbor.vendor,
      neighbor.platform,
      shortInterfaceName(neighbor.remote_interface),
      neighbor.status,
      neighbor.discovery,
    ]);
    row.children[7].className = `neighbor-status ${statusClass(neighbor.status)}`;
    if (neighbor.notes) {
      row.title = neighbor.notes;
    }
    if (managedDevice) {
      row.classList.add("neighbor-row", "managed");
      row.addEventListener("click", () => openManagedDevice(managedDevice.device_id));
    }
    nodes.neighborsBody.append(row);
  }
}

function findManagedNeighbor(neighbor) {
  const ip = neighbor.management_ip || "";
  const name = neighbor.neighbor_name || "";
  return (
    state.devices.find((device) => ip && device.management_ip === ip) ||
    state.devices.find((device) => name && device.hostname === name) ||
    null
  );
}

function appendNeighborAction(row, managedDevice) {
  const cell = document.createElement("td");
  if (!managedDevice) {
    cell.textContent = "Not managed";
    cell.className = "muted";
    row.append(cell);
    return;
  }

  const button = document.createElement("button");
  button.type = "button";
  button.className = "table-action";
  button.textContent = "Detail";
  button.title =
    isCollectable(managedDevice)
      ? "Show device detail, command plan, diagnostics, and collection controls."
      : "Show device detail and command plan. Collection is disabled until access is verified.";
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    openManagedDevice(managedDevice.device_id);
  });
  cell.append(button);
  row.append(cell);
}

async function openManagedDevice(deviceId) {
  await selectDevice(deviceId);
  const collectState = isCollectable(state.selectedDevice) ? "collect enabled" : "collect disabled until access is verified";
  setStatus(`Selected ${deviceId}. ${collectState}.`, true);
  document.querySelector(".detail-panel")?.scrollIntoView({ block: "start", behavior: "smooth" });
}

function collectionReadyMessage(device) {
  if (!device) {
    return "No collection attempted.";
  }
  if (!isCollectable(device)) {
    return [
      `Device: ${device.device_id} (${device.management_ip})`,
      "Collection: disabled",
      "",
      "===== SAFETY NOTICE =====",
      "This neighbor is in inventory for planning and diagnostics, but access method and credentials are not verified.",
      "Command Plan is available. Live collection will remain blocked until Telnet/SSH/API access is explicitly confirmed.",
    ].join("\n");
  }
  return "No collection attempted.";
}

function shortInterfaceName(value) {
  return String(value || "")
    .replace(/^TenGigabitEthernet/i, "Te")
    .replace(/^GigabitEthernet/i, "Gi")
    .replace(/^FastEthernet/i, "Fa")
    .replace(/^Ethernet/i, "Et")
    .replace(/^Port-channel/i, "Po")
    .replace(/^Vlan/i, "Vl");
}

function statusClass(status) {
  return String(status || "").replace(/[^a-z0-9-]/gi, "").toLowerCase();
}

function highestSeverity(findings) {
  const rank = { info: 1, warning: 2, critical: 3 };
  return findings.reduce((highest, item) => (rank[item.severity] > rank[highest] ? item.severity : highest), "info");
}

function severityClass(severity) {
  if (severity === "critical") {
    return "error";
  }
  if (severity === "warning") {
    return "warn";
  }
  return "ok";
}

async function loadAudit() {
  if (!nodes.auditBody) {
    return;
  }
  const payload = await api("/audit-log?limit=100");
  nodes.auditBody.replaceChildren();
  for (const event of payload.events.slice().reverse()) {
    const row = document.createElement("tr");
    const commandText = Array.isArray(event.commands) ? event.commands.join(" | ") : "";
    appendCells(row, [
      event.timestamp,
      event.device_id || event.hostname,
      event.management_ip,
      event.purpose,
      commandText,
    ]);
    const resultCell = document.createElement("td");
    resultCell.append(severityBadge(event.success ? "resolved" : "critical", event.success ? "Success" : "Failure"));
    row.append(resultCell);
    appendCells(row, [event.error_summary]);
    nodes.auditBody.append(row);
  }
}

function appendCells(row, values) {
  for (const value of values) {
    const cell = document.createElement("td");
    cell.textContent = text(value);
    row.append(cell);
  }
}

function activateResultTab(tab) {
  state.activeResultTab = tab;
  for (const button of document.querySelectorAll("[data-result-tab]")) {
    button.classList.toggle("active", button.dataset.resultTab === tab);
  }
  for (const pane of document.querySelectorAll("[data-result-pane]")) {
    pane.classList.toggle("active", pane.dataset.resultPane === tab);
  }
}

function activateDetailTab(tab) {
  state.activeDetailTab = tab;
  for (const button of document.querySelectorAll("[data-detail-tab]")) {
    button.classList.toggle("active", button.dataset.detailTab === tab);
  }
  for (const pane of document.querySelectorAll("[data-detail-pane]")) {
    pane.classList.toggle("active", pane.dataset.detailPane === tab);
  }
}

nodes.refreshDevices?.addEventListener("click", () => {
  loadDevices().catch((error) => setStatus(error.message, false));
});
nodes.dashboardShowAll?.addEventListener("click", () => {
  state.dashboardFilter = "all";
  state.topologyFloorFilter = "all";
  state.topologyVendorFilter = "all";
  state.topologyTierFilter = "all";
  state.topologyAutoFit = false;
  state.topologyZoom = 1;
  renderDashboard();
});
nodes.dashboardShowIssues?.addEventListener("click", () => {
  state.dashboardFilter = "issues";
  state.topologyAutoFit = false;
  state.topologyZoom = 1;
  renderDashboard();
});
nodes.refreshAudit?.addEventListener("click", () => {
  loadAudit().catch((error) => setStatus(error.message, false));
});
nodes.portRefresh?.addEventListener("click", () => {
  loadPorts().catch((error) => setStatus(error.message, false));
});
nodes.portStatusFilter?.addEventListener("change", () => {
  state.portStatusFilter = nodes.portStatusFilter.value;
  renderPortMatrix();
});
nodes.portModeFilter?.addEventListener("change", () => {
  state.portModeFilter = nodes.portModeFilter.value;
  renderPortMatrix();
});
nodes.portVlanFilter?.addEventListener("input", () => {
  state.portVlanFilter = nodes.portVlanFilter.value.trim().toLowerCase();
  renderPortMatrix();
});
nodes.portSearchInput?.addEventListener("input", () => {
  state.portSearchQuery = nodes.portSearchInput.value.trim().toLowerCase();
  renderPortMatrix();
});
nodes.rawSearchInput?.addEventListener("input", () => {
  state.rawSearchQuery = nodes.rawSearchInput.value.trim();
  renderRawOutput();
});
nodes.copyRawOutput?.addEventListener("click", () => {
  navigator.clipboard?.writeText(state.rawOutput || "").then(
    () => setStatus("Raw CLI output copied.", true),
    () => setStatus("Raw CLI output could not be copied.", false),
  );
});
for (const button of document.querySelectorAll("[data-result-tab]")) {
  button.addEventListener("click", () => activateResultTab(button.dataset.resultTab));
}
for (const button of document.querySelectorAll("[data-detail-tab]")) {
  button.addEventListener("click", () => activateDetailTab(button.dataset.detailTab));
}
nodes.checkDevice?.addEventListener("click", () => {
  checkSelectedDevice().catch((error) => renderSummary(error.message, "error"));
});
nodes.loadPlan?.addEventListener("click", () => {
  loadCommandPlan().catch((error) => renderSummary(error.message, "error"));
});
nodes.collect?.addEventListener("click", () => {
  collectSelected().catch((error) => renderSummary(error.message, "error"));
});
nodes.searchButton?.addEventListener("click", () => {
  runSearch().catch((error) => setStatus(error.message, false));
});
nodes.searchInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    runSearch().catch((error) => setStatus(error.message, false));
  }
});
nodes.diagnosePort?.addEventListener("click", () => {
  diagnoseSelectedPort().catch((error) => renderSummary(error.message, "error"));
});
nodes.purposeSelect?.addEventListener("change", () => {
  state.selectedPurpose = nodes.purposeSelect.value;
  state.latestPlan = null;
  state.previewReady = false;
  state.previewAction = "collect";
  renderCommandPlan(null);
  renderCommandPreview(null);
  if (nodes.collect) {
    nodes.collect.disabled = true;
  }
  loadCommandPlan().catch((error) => renderSummary(error.message, "error"));
});
window.addEventListener("resize", () => {
  renderTopologyMap();
});

Promise.all([api("/health"), loadDevices(), loadAudit()])
  .then(([health]) => {
    setStatus(`API connected. ${health.mode}.`, true);
    startTopologyStream();
  })
  .catch((error) => setStatus(error.message, false));
