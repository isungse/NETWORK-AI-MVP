const state = {
  devices: [],
  selectedDevice: null,
  selectedPurpose: "",
  latestPlan: null,
};

const nodes = {
  apiStatus: document.querySelector("#apiStatus"),
  devicesBody: document.querySelector("#devicesBody"),
  selectedDeviceId: document.querySelector("#selectedDeviceId"),
  deviceFacts: document.querySelector("#deviceFacts"),
  purposeSelect: document.querySelector("#purposeSelect"),
  loadPlan: document.querySelector("#loadPlan"),
  collect: document.querySelector("#collect"),
  commandPlan: document.querySelector("#commandPlan"),
  diagnosticSummary: document.querySelector("#diagnosticSummary"),
  diagnosticFindings: document.querySelector("#diagnosticFindings"),
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
  await loadDiagnostics();
  await loadPurposes();
  setStatus(`API connected. ${state.devices.length} devices loaded.`, true);
}

async function selectDevice(deviceId) {
  state.selectedDevice = state.devices.find((device) => device.device_id === deviceId) || null;
  state.latestPlan = null;
  renderDevices();
  renderDeviceFacts(state.selectedDevice);
  renderCommandPlan(null);
  await loadDiagnostics();
  nodes.collectionResult.textContent = "No collection attempted.";
  await loadPurposes();
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
  nodes.collect.disabled = false;
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

async function collectSelected() {
  if (!state.selectedDevice || !state.selectedPurpose) {
    return;
  }

  nodes.collect.disabled = true;
  nodes.collectionResult.textContent = "Collecting read-only command metadata...";
  renderSummary("Collection request in progress.", "warn");

  try {
    const result = await api(
      `/devices/${encodeURIComponent(state.selectedDevice.device_id)}/collect/${encodeURIComponent(state.selectedPurpose)}`,
      { method: "POST" },
    );
    nodes.collectionResult.textContent = formatCollectionResult(result);
    renderSummary(summaryFromResult(result), result.success ? "ok" : "error");
  } catch (error) {
    nodes.collectionResult.textContent = formatCollectionError(error);
    renderSummary(error.message, "error");
  } finally {
    nodes.collect.disabled = false;
    await loadAudit();
    await loadDiagnostics();
  }
}

function formatCollectionResult(result) {
  const lines = [
    `Device: ${result.device_id} (${result.management_ip})`,
    `Purpose: ${result.purpose}`,
    `Result: ${result.success ? "success" : "failure"}    returncode=${text(result.returncode)}    stdout=${text(result.stdout_bytes)} bytes    stderr=${text(result.stderr_bytes)} bytes`,
    `Commands: ${Array.isArray(result.commands) ? result.commands.join(" | ") : "-"}`,
    "",
    "===== STDOUT =====",
    result.stdout || "(no stdout)",
  ];

  if (!result.success && result.stderr) {
    lines.push("", "===== STDERR =====", result.stderr);
  }

  if (result.error_summary) {
    lines.push("", "===== ERROR SUMMARY =====", result.error_summary);
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
nodes.loadPlan.addEventListener("click", () => {
  loadCommandPlan().catch((error) => renderSummary(error.message, "error"));
});
nodes.collect.addEventListener("click", () => {
  collectSelected().catch((error) => renderSummary(error.message, "error"));
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
