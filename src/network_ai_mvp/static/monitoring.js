const MONITORING_STORAGE_KEY = "networkAiMvp.collectionResult.v1";

const nodes = {
  status: document.querySelector("#monitorStatus"),
  meta: document.querySelector("#monitorMeta"),
  result: document.querySelector("#monitorResult"),
};

function renderMonitoringResult() {
  const raw = localStorage.getItem(MONITORING_STORAGE_KEY);
  if (!raw) {
    nodes.status.textContent = "Waiting for collection result...";
    nodes.meta.textContent = "No result mirrored yet";
    nodes.result.textContent = "Run Collect in the main UI to mirror the latest result here.";
    return;
  }

  try {
    const payload = JSON.parse(raw);
    nodes.result.innerHTML = payload.html || escapeHtml(payload.text || "");
    nodes.status.textContent = "Mirroring latest Collection Result.";
    nodes.meta.textContent = formatMeta(payload);
  } catch {
    nodes.status.textContent = "Monitoring data could not be parsed.";
    nodes.meta.textContent = "Invalid local mirror data";
    nodes.result.textContent = raw;
  }
}

function formatMeta(payload) {
  const parts = [];
  if (payload.device_id) {
    parts.push(payload.device_id);
  }
  if (payload.management_ip) {
    parts.push(payload.management_ip);
  }
  if (payload.purpose) {
    parts.push(payload.purpose);
  }
  if (payload.updated_at) {
    parts.push(new Date(payload.updated_at).toLocaleString());
  }
  return parts.length ? parts.join(" | ") : "No metadata";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

window.addEventListener("storage", (event) => {
  if (event.key === MONITORING_STORAGE_KEY) {
    renderMonitoringResult();
  }
});

window.addEventListener("focus", renderMonitoringResult);
renderMonitoringResult();
