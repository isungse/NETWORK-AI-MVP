const state = {
  devices: [],
  selectedDevice: null,
  selectedPurpose: "",
  latestPlan: null,
  selectedPort: null,
};

const MONITORING_STORAGE_KEY = "networkAiMvp.collectionResult.v1";

const nodes = {
  apiStatus: document.querySelector("#apiStatus"),
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

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const message = payload?.detail || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return payload;
}

function setStatus(message, ok = true) {
  nodes.apiStatus.textContent = message;
  nodes.apiStatus.className = ok ? "status-ok" : "status-fail";
}

function text(value) {
  return value === null || value === undefined || value === "" ? "-" : String(value);
}

function renderDevices() {
  nodes.devicesBody.replaceChildren();
  for (const device of state.devices) {
    const row = document.createElement("tr");
    row.className = "device-row";
    row.dataset.deviceId = device.device_id;
    if (state.selectedDevice?.device_id === device.device_id) {
      row.classList.add("selected");
    }
    appendCells(row, [
      device.device_id,
      device.hostname,
      device.management_ip,
      device.vendor,
      device.role,
      device.access_method,
    ]);
    row.addEventListener("click", () => selectDevice(device.device_id));
    nodes.devicesBody.append(row);
  }
}

function renderDeviceFacts(device) {
  nodes.selectedDeviceId.textContent = device ? device.device_id : "No device selected";
  nodes.deviceFacts.replaceChildren();
  if (!device) {
    return;
  }

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
  if (!state.selectedDevice && state.devices.length) {
    state.selectedDevice = state.devices[0];
  } else if (state.selectedDevice) {
    state.selectedDevice = state.devices.find((item) => item.device_id === state.selectedDevice.device_id) || null;
  }
  renderDevices();
  renderDeviceFacts(state.selectedDevice);
  renderCheckResults(null);
  updateCheckButton();
  await loadDiagnostics();
  await loadNeighbors();
  await loadPurposes();
  renderPortDetail(null);
  setStatus(`API connected. ${state.devices.length} devices loaded.`, true);
}

async function selectDevice(deviceId) {
  state.selectedDevice = state.devices.find((device) => device.device_id === deviceId) || null;
  state.latestPlan = null;
  state.selectedPort = null;
  renderDevices();
  renderDeviceFacts(state.selectedDevice);
  renderCommandPlan(null);
  renderPortDetail(null);
  renderCheckResults(null);
  updateCheckButton();
  await loadDiagnostics();
  await loadNeighbors();
  await loadPurposes();
  setCollectionResultText(collectionReadyMessage(state.selectedDevice));
}

function updateCheckButton() {
  nodes.checkDevice.disabled = !state.selectedDevice || state.selectedDevice.access_method !== "telnet";
}

async function loadPurposes() {
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
  if (state.selectedPurpose) {
    await loadCommandPlan();
  }
}

async function loadCommandPlan() {
  if (!state.selectedDevice || !state.selectedPurpose) {
    return;
  }
  state.latestPlan = await api(
    `/devices/${encodeURIComponent(state.selectedDevice.device_id)}/command-plan/${encodeURIComponent(state.selectedPurpose)}`,
  );
  renderCommandPlan(state.latestPlan);
  nodes.collect.disabled = state.selectedDevice.access_method !== "telnet";
}

function renderCommandPlan(plan) {
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

async function checkSelectedDevice() {
  if (!state.selectedDevice) {
    return;
  }
  if (state.selectedDevice.access_method !== "telnet") {
    renderCheckResults([{
      label: "CHECK",
      status: "fail",
      detail: "This device is not enabled for read-only collection.",
    }]);
    return;
  }

  nodes.checkDevice.disabled = true;
  state.selectedPurpose = "check";
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
    renderSummary(error.message, "error");
  } finally {
    updateCheckButton();
    await loadAudit();
    await loadDiagnostics();
  }
}

function renderCheckResults(items) {
  nodes.checkResults.replaceChildren();
  const rows = items || [
    { label: "저속 협상 포트 자동 탐지", status: "unknown", detail: "CHECK를 실행하면 결과가 표시됩니다." },
    { label: "CRC/error 많은 포트 탐지", status: "unknown", detail: "CHECK를 실행하면 결과가 표시됩니다." },
    { label: "uplink/LACP/trunk 이상 탐지", status: "unknown", detail: "CHECK를 실행하면 결과가 표시됩니다." },
    { label: "IP-MAC-Port 자동 추적", status: "unknown", detail: "CHECK를 실행하면 결과가 표시됩니다." },
    { label: "구성도와 실제 연결 상태 불일치 탐지", status: "unknown", detail: "CHECK를 실행하면 결과가 표시됩니다." },
  ];
  for (const item of rows) {
    const article = document.createElement("article");
    const status = checkStatus(item.status);
    article.className = `check-item ${status}`;

    const statusNode = document.createElement("div");
    statusNode.className = "check-status";
    statusNode.textContent = status;

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
  return ["ok", "warn", "fail", "unknown"].includes(status) ? status : "unknown";
}

async function runSearch() {
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
    document.querySelector(".port-detail-panel")?.scrollIntoView({ block: "start", behavior: "smooth" });
    return;
  }
  if (result.type === "neighbor") {
    renderReferencePortDetail(result);
    document.querySelector(".port-detail-panel")?.scrollIntoView({ block: "start", behavior: "smooth" });
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

function renderPortDetail(port, message = "Search for a port, IP, MAC, or device to inspect stored parsed state.") {
  state.selectedPort = port;
  nodes.portDetailFacts.replaceChildren();
  nodes.diagnosePort.disabled = !state.selectedDevice || !port;
  if (!port) {
    nodes.portDetailState.className = "summary-box warn";
    nodes.portDetailState.textContent = message;
    return;
  }

  const facts = [
    ["Interface", port.interface],
    ["Status", port.status],
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
}

function renderReferencePortDetail(result) {
  state.selectedPort = null;
  nodes.portDetailFacts.replaceChildren();
  nodes.diagnosePort.disabled = !state.selectedDevice;
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
}

async function diagnoseSelectedPort() {
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
  renderSummary("Port diagnostic plan loaded. Review the allowlisted commands, then click Collect when ready.", "warn");
}

function listText(values) {
  return Array.isArray(values) && values.length ? values.join(", ") : "-";
}

async function collectSelected() {
  if (!state.selectedDevice || !state.selectedPurpose) {
    return;
  }
  if (state.selectedDevice.access_method !== "telnet") {
    renderSummary("Collection is disabled until this device access method and credentials are verified.", "warn");
    return;
  }

  nodes.collect.disabled = true;
  setCollectionResultText("Collecting read-only command metadata...");
  renderSummary("Collection request in progress.", "warn");

  try {
    const result = await api(
      `/devices/${encodeURIComponent(state.selectedDevice.device_id)}/collect/${encodeURIComponent(state.selectedPurpose)}`,
      { method: "POST" },
    );
    setCollectionResultHtml(formatCollectionResultHtml(result));
    renderSummary(summaryFromResult(result), result.success ? "ok" : "error");
  } catch (error) {
    setCollectionResultHtml(escapeHtml(formatCollectionError(error)));
    renderSummary(error.message, "error");
  } finally {
    nodes.collect.disabled = false;
    await loadAudit();
    await loadDiagnostics();
  }
}

function setCollectionResultText(value) {
  nodes.collectionResult.textContent = value;
  publishMonitoringResult(nodes.collectionResult.innerHTML, nodes.collectionResult.textContent);
}

function setCollectionResultHtml(value) {
  nodes.collectionResult.innerHTML = value;
  publishMonitoringResult(nodes.collectionResult.innerHTML, nodes.collectionResult.textContent);
}

function publishMonitoringResult(htmlValue, textValue) {
  const payload = {
    html: htmlValue,
    text: textValue,
    updated_at: new Date().toISOString(),
    device_id: state.selectedDevice?.device_id || "",
    hostname: state.selectedDevice?.hostname || "",
    management_ip: state.selectedDevice?.management_ip || "",
    purpose: state.selectedPurpose || "",
  };
  localStorage.setItem(MONITORING_STORAGE_KEY, JSON.stringify(payload));
}

function formatCollectionResultHtml(result) {
  const endpointSummary = formatEndpointIpSummary(result);
  const interfaceSummary = formatInterfaceFindingSummary(result);
  const lines = [
    `Device: ${result.device_id} (${result.management_ip})`,
    `Purpose: ${result.purpose}`,
    `Result: ${result.success ? "success" : "failure"}    returncode=${text(result.returncode)}    stdout=${text(result.stdout_bytes)} bytes    stderr=${text(result.stderr_bytes)} bytes`,
    `Commands: ${Array.isArray(result.commands) ? result.commands.join(" | ") : "-"}`,
  ];

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
    lines.push(`[${String(item.status || "unknown").toUpperCase()}] ${item.label}: ${item.detail}`);
  }

  if (Array.isArray(result.parsed_ports) && result.parsed_ports.length) {
    lines.push("", "===== INTERFACE FINDINGS =====", formatInterfaceFindingSummaryFromPorts(result.parsed_ports));
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
  if (Array.isArray(result.parsed_ports) && result.parsed_ports.length) {
    return formatInterfaceFindingSummaryFromPorts(result.parsed_ports);
  }
  if (!Array.isArray(result.commands) || !result.commands.includes("show interfaces status")) {
    return "";
  }

  const sections = commandSections(result.stdout || "");
  const statusRows = parseInterfaceStatus(sections.get("show interfaces status") || "");
  const counterRows = parseInterfaceErrorCounters(sections.get("show interfaces counters errors") || "");
  if (!statusRows.length && !counterRows.length) {
    return "";
  }

  const statusByPort = new Map(statusRows.map((row) => [row.port, row]));
  const lowSpeedRows = statusRows.filter((row) => {
    const speed = speedMbps(row.speed);
    return row.status === "connected" && speed !== null && speed < 1000;
  });
  const disabledRows = statusRows.filter((row) => row.status === "disabled" || row.status === "errdisabled");
  const highCounterRows = counterRows.filter((row) => Math.max(row.fcs, row.rx, row.runts, row.tx) >= 1000);

  const lines = [];
  if (lowSpeedRows.length) {
    lines.push("LOW-SPEED CONNECTED PORTS");
    for (const row of lowSpeedRows) {
      lines.push(`- ${row.port}  status=${row.status}  vlan=${row.vlan}  duplex=${row.duplex}  speed=${row.speed}`);
    }
  } else {
    lines.push("LOW-SPEED CONNECTED PORTS");
    lines.push("- none found in collected interface status");
  }

  if (disabledRows.length) {
    lines.push("", "DISABLED PORTS");
    for (const row of disabledRows) {
      lines.push(`- ${row.port}  status=${row.status}  vlan=${row.vlan}  speed=${row.speed}`);
    }
  }

  if (highCounterRows.length) {
    lines.push("", "HIGH ERROR COUNTERS");
    for (const row of highCounterRows) {
      const status = statusByPort.get(row.port);
      const state = status ? `  current=${status.status}/${status.speed}` : "";
      lines.push(`- ${row.port}${state}  FCS=${row.fcs}  Rx=${row.rx}  Runts=${row.runts}  Tx=${row.tx}`);
    }
  }

  return lines.join("\n");
}

function formatInterfaceFindingSummaryFromPorts(ports) {
  const lowSpeedRows = ports.filter((port) => (
    port.status === "connected" &&
    Number.isFinite(port.speed_mbps) &&
    port.speed_mbps < 1000
  ));
  const disabledRows = ports.filter((port) => port.status === "disabled" || port.status === "errdisabled");
  const highCounterRows = ports.filter((port) => Math.max(
    Number(port.fcs_errors || 0),
    Number(port.rx_errors || 0),
    Number(port.runts || 0),
    Number(port.tx_errors || 0),
  ) >= 1000);

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

function parseInterfaceStatus(section) {
  const statusTokens = new Set(["connected", "notconnect", "disabled", "errdisabled"]);
  const rows = [];
  for (const line of section.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("Port ") || /[>#]\s*$/.test(trimmed)) {
      continue;
    }
    const parts = trimmed.split(/\s+/);
    const statusIndex = parts.findIndex((part, index) => index > 0 && statusTokens.has(part.toLowerCase()));
    if (statusIndex < 1 || parts.length < statusIndex + 4) {
      continue;
    }
    rows.push({
      port: shortInterfaceName(parts[0]),
      name: parts.slice(1, statusIndex).join(" "),
      status: parts[statusIndex].toLowerCase(),
      vlan: parts[statusIndex + 1],
      duplex: parts[statusIndex + 2],
      speed: parts[statusIndex + 3],
    });
  }
  return rows;
}

function parseInterfaceErrorCounters(section) {
  const rows = [];
  for (const line of section.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("Port ") || /[>#]\s*$/.test(trimmed)) {
      continue;
    }
    const parts = trimmed.split(/\s+/);
    if (parts.length < 8) {
      continue;
    }
    rows.push({
      port: shortInterfaceName(parts[0]),
      fcs: Number(parts[1] || 0),
      align: Number(parts[2] || 0),
      symbol: Number(parts[3] || 0),
      rx: Number(parts[4] || 0),
      runts: Number(parts[5] || 0),
      giants: Number(parts[6] || 0),
      tx: Number(parts[7] || 0),
    });
  }
  return rows;
}

function speedMbps(value) {
  const normalized = String(value || "").toLowerCase().replace(/^a-/, "");
  const match = normalized.match(/^(\d+)(m|g)$/);
  if (!match) {
    return null;
  }
  const amount = Number(match[1]);
  return match[2] === "g" ? amount * 1000 : amount;
}

function formatEndpointIpSummary(result) {
  if (Array.isArray(result.parsed_ports) && result.parsed_ports.length) {
    return formatEndpointIpSummaryFromPorts(result.parsed_ports);
  }
  if (!Array.isArray(result.commands) || !result.commands.includes("show interfaces description")) {
    return "";
  }
  if (!result.commands.includes("show mac address-table") || !result.commands.includes("show ip arp")) {
    return "";
  }

  const sections = commandSections(result.stdout || "");
  const descriptions = parseInterfaceDescriptions(sections.get("show interfaces description") || "");
  const macEntries = parseMacAddressTable(sections.get("show mac address-table") || "");
  const arpEntries = parseIpArp(sections.get("show ip arp") || "");
  if (!descriptions.length || !macEntries.length || !arpEntries.length) {
    return "";
  }

  const ipsByMac = new Map();
  for (const entry of arpEntries) {
    if (!ipsByMac.has(entry.mac)) {
      ipsByMac.set(entry.mac, new Set());
    }
    ipsByMac.get(entry.mac).add(entry.ip);
  }

  const endpointsByInterface = new Map();
  for (const entry of macEntries) {
    const ips = ipsByMac.get(entry.mac);
    if (!ips || !ips.size) {
      continue;
    }
    const interfaceName = shortInterfaceName(entry.interfaceName);
    if (!endpointsByInterface.has(interfaceName)) {
      endpointsByInterface.set(interfaceName, []);
    }
    for (const ip of ips) {
      endpointsByInterface.get(interfaceName).push({ ip, mac: entry.macText });
    }
  }

  const lines = [];
  for (const item of descriptions) {
    const interfaceName = shortInterfaceName(item.interfaceName);
    const endpoints = endpointsByInterface.get(interfaceName) || [];
    if (!endpoints.length) {
      continue;
    }
    lines.push(`${interfaceName}  ${item.status}/${item.protocol}  ${item.description || "-"}`);
    for (const endpoint of endpoints.sort((left, right) => ipSortKey(left.ip) - ipSortKey(right.ip))) {
      lines.push(`  - ip=${endpoint.ip.padEnd(15)} mac=${endpoint.mac}`);
    }
  }

  return lines.join("\n");
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

function commandSections(stdout) {
  const sections = new Map();
  let current = "";
  let buffer = [];

  for (const line of String(stdout || "").split(/\r?\n/)) {
    const match = line.match(/^===== (.+?) =====$/);
    if (match) {
      if (current) {
        sections.set(current, buffer.join("\n"));
      }
      current = match[1].trim();
      buffer = [];
      continue;
    }
    if (current) {
      buffer.push(line);
    }
  }

  if (current) {
    sections.set(current, buffer.join("\n"));
  }
  return sections;
}

function parseInterfaceDescriptions(section) {
  const rows = [];
  for (const line of section.split(/\r?\n/)) {
    const trimmed = line.trimEnd();
    if (!trimmed || trimmed.startsWith("Interface ") || /[>#]\s*$/.test(trimmed)) {
      continue;
    }
    const match = trimmed.match(/^(\S+)\s+(\S+)\s+(\S+)\s*(.*)$/);
    if (!match) {
      continue;
    }
    rows.push({
      interfaceName: match[1],
      status: match[2],
      protocol: match[3],
      description: match[4].trim(),
    });
  }
  return rows;
}

function parseMacAddressTable(section) {
  const rows = [];
  for (const line of section.split(/\r?\n/)) {
    const match = line.match(/^\s*\S+\s+([0-9a-f]{4}[.:-][0-9a-f]{4}[.:-][0-9a-f]{4})\s+\S+.*\s+(\S+)\s*$/i);
    if (!match || /^CPU$/i.test(match[2])) {
      continue;
    }
    rows.push({
      mac: normalizeMac(match[1]),
      macText: canonicalMac(match[1]),
      interfaceName: match[2],
    });
  }
  return rows;
}

function parseIpArp(section) {
  const rows = [];
  for (const line of section.split(/\r?\n/)) {
    const match = line.match(/\b(\d{1,3}(?:\.\d{1,3}){3})\s+\S+\s+([0-9a-f]{4}[.:-][0-9a-f]{4}[.:-][0-9a-f]{4})\s+/i);
    if (!match) {
      continue;
    }
    rows.push({
      ip: match[1],
      mac: normalizeMac(match[2]),
    });
  }
  return rows;
}

function normalizeMac(value) {
  return String(value || "").replace(/[^0-9a-f]/gi, "").toLowerCase();
}

function canonicalMac(value) {
  const normalized = normalizeMac(value);
  if (normalized.length !== 12) {
    return String(value || "");
  }
  return `${normalized.slice(0, 4)}.${normalized.slice(4, 8)}.${normalized.slice(8, 12)}`;
}

function ipSortKey(value) {
  return String(value || "")
    .split(".")
    .reduce((sum, octet) => (sum * 256) + Number(octet || 0), 0);
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
  nodes.diagnosticSummary.className = `summary-box ${className}`;
  nodes.diagnosticSummary.textContent = message;
}

async function loadDiagnostics() {
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
    const badge = document.createElement("span");
    badge.className = "finding-severity";
    badge.textContent = finding.severity;
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
    managedDevice.access_method === "telnet"
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
  const access = state.selectedDevice?.access_method || "unknown";
  const collectState = access === "telnet" ? "collect enabled" : "collect disabled until access is verified";
  setStatus(`Selected ${deviceId}. ${collectState}.`, true);
  document.querySelector(".detail-panel")?.scrollIntoView({ block: "start", behavior: "smooth" });
}

function collectionReadyMessage(device) {
  if (!device) {
    return "No collection attempted.";
  }
  if (device.access_method !== "telnet") {
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
      event.success ? "success" : "failure",
      event.error_summary,
    ]);
    row.children[5].className = event.success ? "status-ok" : "status-fail";
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

nodes.refreshDevices.addEventListener("click", () => {
  loadDevices().catch((error) => setStatus(error.message, false));
});
nodes.refreshAudit.addEventListener("click", () => {
  loadAudit().catch((error) => setStatus(error.message, false));
});
nodes.checkDevice.addEventListener("click", () => {
  checkSelectedDevice().catch((error) => renderSummary(error.message, "error"));
});
nodes.loadPlan.addEventListener("click", () => {
  loadCommandPlan().catch((error) => renderSummary(error.message, "error"));
});
nodes.collect.addEventListener("click", () => {
  collectSelected().catch((error) => renderSummary(error.message, "error"));
});
nodes.searchButton.addEventListener("click", () => {
  runSearch().catch((error) => setStatus(error.message, false));
});
nodes.searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    runSearch().catch((error) => setStatus(error.message, false));
  }
});
nodes.diagnosePort.addEventListener("click", () => {
  diagnoseSelectedPort().catch((error) => renderSummary(error.message, "error"));
});
nodes.purposeSelect.addEventListener("change", () => {
  state.selectedPurpose = nodes.purposeSelect.value;
  state.latestPlan = null;
  renderCommandPlan(null);
  nodes.collect.disabled = true;
  loadCommandPlan().catch((error) => renderSummary(error.message, "error"));
});

Promise.all([api("/health"), loadDevices(), loadAudit()])
  .then(([health]) => setStatus(`API connected. ${health.mode}.`, true))
  .catch((error) => setStatus(error.message, false));
