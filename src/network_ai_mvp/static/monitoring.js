const nodes = {
  status: document.querySelector("#monitorStatus"),
  meta: document.querySelector("#monitorMeta"),
  result: document.querySelector("#monitorResult"),
};

async function loadLatestMonitoringResult() {
  const response = await fetch("/monitoring/latest", {
    headers: { Accept: "application/json" },
  });
  const payload = await response.json();
  renderMonitoringResult(payload);
}

function subscribeMonitoringEvents() {
  if (!window.EventSource) {
    nodes.status.textContent = "Server events are not supported by this browser.";
    return;
  }

  const events = new EventSource("/events/monitoring");
  events.onopen = () => {
    nodes.status.textContent = "Connected to server monitoring stream.";
  };
  events.onmessage = (event) => {
    try {
      renderMonitoringResult(JSON.parse(event.data));
    } catch {
      nodes.status.textContent = "Monitoring event could not be parsed.";
      nodes.meta.textContent = "Invalid server event";
      nodes.result.textContent = event.data;
    }
  };
  events.onerror = () => {
    nodes.status.textContent = "Waiting for server monitoring stream...";
  };
}

function renderMonitoringResult(payload) {
  if (!payload?.available) {
    nodes.status.textContent = "Waiting for collection result...";
    nodes.meta.textContent = "No server-side result yet";
    nodes.result.textContent = payload?.text || "Run Collect or CHECK in the main UI to stream the latest result here.";
    return;
  }

  nodes.result.textContent = payload.text || "";
  nodes.status.textContent = payload.success ? "Latest server collection succeeded." : "Latest server collection failed.";
  nodes.meta.textContent = formatMeta(payload);
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

loadLatestMonitoringResult().catch((error) => {
  nodes.status.textContent = "Monitoring snapshot could not be loaded.";
  nodes.meta.textContent = error.message;
});
subscribeMonitoringEvents();
