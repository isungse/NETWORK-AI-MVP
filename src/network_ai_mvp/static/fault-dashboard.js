"use strict";
const $ = (selector) => document.querySelector(selector);
const LABELS = {
  critical: "중대 장애",
  unknown: "상태 확인 불가",
  pending: "재확인 중",
  normal: "정상",
  maintenance: "관리자 비활성",
};
const ICONS = {
  critical: "● !",
  unknown: "?",
  pending: "◷",
  normal: "✓",
  maintenance: "Ⅱ",
};
let dashboard,
  selectedDevice,
  selectedPort,
  proposal,
  detailGeneration = 0;
let fetchInFlight = false;
let floorFilter = "";
let slotEditor = null;
let slotAliasSaving = false;
const time = (value) =>
  value
    ? new Intl.DateTimeFormat("ko-KR", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
        timeZone: "Asia/Seoul",
      }).format(new Date(value))
    : "확인 기록 없음";
const floorLabel = (floor) =>
  !floor
    ? "층 미설정"
    : /^B\d+F$/i.test(floor)
      ? `지하 ${floor.slice(1, -1)}층`
      : /^\d+F$/i.test(floor)
        ? `${floor.slice(0, -1)}층`
        : floor;
const locationText = (d) =>
  `${d.building || "건물 미설정"} · ${floorLabel(d.floor)}`;
const portStatus = (value) =>
  ({
    connected: "연결",
    up: "연결",
    notconnect: "연결 없음",
    down: "연결 끊김",
    disabled: "관리상 비활성",
    "administratively down": "관리상 비활성",
    errdisabled: "오류로 비활성",
  })[value] ||
  value ||
  "미확인";
function node(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
}
function badge(status) {
  return node(
    "span",
    `badge ${status}`,
    `${ICONS[status] || "?"} ${LABELS[status] || "미확인"}`,
  );
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    signal: AbortSignal.timeout(options.method === "POST" ? 180000 : 15000),
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    const translations = {
      "Approval code is invalid.": "승인 코드가 일치하지 않습니다.",
      "Change proposal expired. Review the live port state again.":
        "변경 계획이 만료되었습니다. 포트 상태를 다시 확인하세요.",
      "This change proposal has already been used.":
        "이미 사용한 변경 계획입니다. 새 계획을 확인하세요.",
      "Controlled port changes are disabled for this runtime.":
        "이 서버에서는 포트 변경이 비활성화되어 있습니다.",
    };
    throw new Error(
      translations[data.detail] ||
        (typeof data.detail === "string"
          ? data.detail
          : "요청을 처리하지 못했습니다."),
    );
  }
  return data;
}
function post(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
function slotHeading(device, slot, base, tag = "div") {
  const header = node("div", "module-heading");
  const title = node(tag, "module-label", FaultPanel.slotTitle(base, device.slot_aliases?.[slot]));
  title.dataset.slotTitle = slot;
  title.dataset.deviceId = device.device_id;
  title.dataset.baseTitle = base;
  header.append(title);
  if (device.slot_alias_editable && device.slot_alias_slots?.includes(slot)) {
    const edit = node("button", "module-edit", "✎ 편집");
    edit.type = "button";
    edit.dataset.slot = slot;
    edit.dataset.deviceId = device.device_id;
    edit.setAttribute("aria-label", `${device.hostname} · ${base} 별칭 편집`);
    edit.onclick = () => {
      slotEditor = { deviceId: device.device_id, slot, base,
        expectedAlias: device.slot_aliases?.[slot] || "",
        inDetail: Boolean(edit.closest("#deviceDialog")) };
      $("#slotAliasTarget").textContent = `${device.hostname} · ${base}`;
      $("#slotAliasInput").value = slotEditor.expectedAlias;
      $("#slotAliasResult").textContent = "";
      updateSlotAliasPreview();
      $("#slotAliasDialog").showModal();
      $("#slotAliasInput").focus();
    };
    header.append(edit);
  }
  return header;
}
function updateSlotAliasPreview() {
  if (slotEditor)
    $("#slotAliasPreview").textContent = FaultPanel.slotTitle(slotEditor.base, $("#slotAliasInput").value.trim());
}
async function saveSlotAlias(event) {
  event.preventDefault();
  if (!slotEditor || slotAliasSaving) return;
  slotAliasSaving = true;
  const controls = [...$("#slotAliasDialog").querySelectorAll("button, input")];
  controls.forEach((control) => { control.disabled = true; });
  $("#slotAliasResult").textContent = "저장 중…";
  const editor = slotEditor;
  try {
    const result = await post(`/fault-monitor/devices/${encodeURIComponent(editor.deviceId)}/slots/${editor.slot}/alias`, {
      alias: $("#slotAliasInput").value, expected_alias: editor.expectedAlias,
    });
    for (const device of [...(dashboard?.devices || []), selectedDevice].filter(Boolean)) {
      if (device.device_id === editor.deviceId) {
        device.slot_aliases ||= {};
        device.slot_aliases[editor.slot] = result.alias;
      }
    }
    for (const title of document.querySelectorAll("[data-slot-title]")) {
      if (title.dataset.deviceId === editor.deviceId && title.dataset.slotTitle === editor.slot)
        title.textContent = FaultPanel.slotTitle(title.dataset.baseTitle, result.alias);
    }
    $("#slotAliasDialog").close();
  } catch (error) {
    $("#slotAliasResult").textContent = `저장하지 못했습니다: ${error.message}`;
  } finally {
    slotAliasSaving = false;
    controls.forEach((control) => { control.disabled = false; });
  }
}
function elapsed(seconds) {
  if (seconds < 60) return "방금";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}분 전`;
  return `${Math.floor(seconds / 3600)}시간 전`;
}
function connectionEvidence(event) {
  const physical = event.physical_confirmed ? "물리 연결 확인 · " : "";
  if (event.source === "observation")
    return `${physical}상태 변화로 발견 · ${time(event.interval_start)} 이후~${time(event.at || event.connected_at)} 사이`;
  if (event.source === "device_log_unverified")
    return `장비 로그 · 시계 보정 불가 · 장비 시각 ${time(event.device_at)}`;
  const correction = Math.abs(event.clock_offset_seconds || 0) >= 30
    ? ` · 장비 시각 ${time(event.device_at)} · 시계 차이 약 ${Math.round(Math.abs(event.clock_offset_seconds) / 60)}분 보정`
    : "";
  return `${physical}연결 로그 · 서버 시각 기준(수집 지연 오차 포함)${correction}`;
}
function markRecentConnection(button, device, port) {
  const connection = FaultPanel.portView(device, port).connection;
  if (!connection) return;
  button.classList.add("recent-connection");
  const marker = node("span", "connection-marker connection-marker-new", "NEW");
  marker.setAttribute("aria-hidden", "true");
  button.append(marker);
  const description = `물리 연결 확인 · ${time(connection.connected_at)} · ${elapsed(connection.age_seconds)} · ${connection.connection_count}회 · ${connectionEvidence(connection)}`;
  button.title += ` · ${description}`;
  button.setAttribute("aria-label", `${button.getAttribute("aria-label")} · ${description}`);
}
function renderRecentConnections(data) {
  const rows = [];
  for (const d of data.devices) {
    if (floorFilter && JSON.stringify([d.building || "건물 미설정", d.floor || "층 미설정"]) !== floorFilter) continue;
    for (const event of Object.values(d.recent_connections || {}))
      if (event.physical_confirmed === true) rows.push({ d, event });
  }
  rows.sort((a, b) => b.event.connected_at.localeCompare(a.event.connected_at));
  $("#recentConnectionSummary").textContent = `최근 24시간 물리 연결 · ${rows.length}개${floorFilter ? " · 선택한 층" : " · 전체 장비"}`;
  const root = $("#recentConnectionList");
  root.replaceChildren();
  if (!rows.length) {
    root.append(node("p", "muted", data.reference_only
      ? "참고 데이터에서는 최근 연결을 표시하지 않습니다."
      : "최근 24시간 내 물리 연결이 확인된 포트가 없습니다. 케이블 연결을 확인한 기록에만 NEW를 표시합니다."));
  } else {
    const wrap = node("div", "table-scroll connection-table-scroll"), table = node("table", "port-table");
    const head = node("tr");
    for (const label of ["장비 · 위치", "포트", "연결 시각 · 근거", "현재 상태", "24시간 연결 횟수"]) head.append(node("th", "", label));
    const thead = node("thead"); thead.append(head); table.append(thead);
    const body = node("tbody");
    for (const { d, event } of rows) {
      const row = node("tr"), identity = node("td", "", `${d.hostname} · ${locationText(d)}`), target = node("td");
      const link = node("button", "target-chip recent-connection", event.interface);
      link.onclick = () => openDevice(d.device_id, event.interface);
      target.append(link);
      const when = node("td", "", `${time(event.connected_at)} · ${elapsed(event.age_seconds)}`);
      when.append(node("small", "connection-evidence", connectionEvidence(event)));
      const port = (d.panel_ports || d.ports || []).find((p) => FaultPanel.shortName(p.interface) === event.interface);
      row.append(identity, target, when,
        node("td", "", d.port_data_current && port ? portStatus(port.status) : "현재 상태 미확인"),
        node("td", "", `${event.connection_count}회${event.repeated ? " · 반복 연결 확인 필요" : ""}`));
      body.append(row);
    }
    table.append(body); wrap.append(table); root.append(wrap);
  }
  const unavailable = data.devices.filter((d) => {
    const status = d.connection_log_status;
    return !status?.success || !status.clock_verified ||
      Date.parse(data.generated_at) - Date.parse(status.checked_at) > data.settings.stale_after_seconds * 1000;
  }).length;
  if (unavailable && !data.reference_only)
    root.append(node("p", "muted", `${unavailable}대의 연결 로그 또는 장비 시각 근거가 없거나 오래되었습니다. 상태 수집 사이의 짧은 연결·해제는 누락될 수 있습니다.`));
}
async function loadConnectionHistory(deviceId, interfaceName, root) {
  try {
    const result = await api(`/fault-monitor/devices/${encodeURIComponent(deviceId)}/ports/${encodeURIComponent(interfaceName)}/connections`);
    if (!root.isConnected) return;
    root.replaceChildren(node("h4", "", "연결 · 해제 이력"));
    if (result.reference_only) root.append(node("p", "muted", "참고 데이터 · 실시간 이력 확인 불가"));
    for (const event of result.events) {
      const label = event.state === "up"
        ? (event.physical_confirmed ? "물리 연결 확인" : "링크 연결·복구 · 물리 연결 미확인") : "연결 해제";
      const row = node("p", "connection-history-item", `${time(event.at)} · ${label}`);
      row.append(node("small", "connection-evidence", connectionEvidence(event)));
      if (event.physical_confirmation_note && event.physical_confirmed)
        row.append(node("small", "connection-evidence", event.physical_confirmation_note));
      if (!result.reference_only && event.state === "up" && event.source !== "device_log_unverified") {
        const confirm = node("button", "target-chip", event.physical_confirmed ? "물리 연결 확인 취소" : "실제 케이블 연결 확인");
        confirm.type = "button";
        confirm.title = "이 연결 시각에 실제로 케이블을 새로 연결했을 때만 확인하세요. NEW는 확인 버튼을 누른 시각이 아닌 연결 시각부터 24시간 표시됩니다.";
        confirm.onclick = async () => {
          confirm.disabled = true;
          try {
            await post("/fault-monitor/physical-connections", {device_id: deviceId, interface: interfaceName,
              event_id: event.id, confirmed: !event.physical_confirmed, note: "운영 화면에서 실제 케이블 연결 여부 확인"});
            await refresh();
          } catch (error) {
            row.append(node("small", "notice error", error.message));
            confirm.disabled = false;
          }
        };
        row.append(confirm);
      }
      root.append(row);
    }
    if (!result.events.length) root.append(node("p", "muted", "기록된 연결·해제 이력이 없습니다. 최초 연결 상태만으로 연결 시각을 추정하지 않습니다."));
    root.append(node("p", "muted", `최근 ${result.limit}건 · ${result.retention_days}일 보관 · 연결자 신원은 별도 자산·인증 정보 필요`));
  } catch (error) {
    if (root.isConnected) root.replaceChildren(node("p", "notice error", `연결 이력을 확인하지 못했습니다: ${error.message}`));
  }
}
function deviceButton(device) {
  const b = node("button", "device-link", device.hostname);
  b.onclick = () => openDevice(device.device_id);
  return b;
}
function metric(label, value, type, key) {
  const box = node(
    "div",
    `metric ${type || ""} ${Number(value) > 0 ? (key === "unknown_devices" ? "has-unknown" : "has-fault") : ""}`,
  );
  box.append(node("span", "metric-label", label));
  const v = node(
    "strong",
    "metric-value",
    type === "time" ? time(value) : (value ?? "—"),
  );
  if (type !== "time")
    v.append(node("small", "", key.includes("faults") ? "건" : "대"));
  box.append(v);
  return box;
}
function issueElement(issue) {
  const row = node("div", "issue");
  for (const [label, text, cls] of [
    [
      "문제 유형",
      `${issue.interface ? issue.interface + " · " : ""}${issue.label}`,
      "problem",
    ],
    ["영향 범위", issue.impact],
    ["최초 감지", issue.first_seen ? time(issue.first_seen) : "확인되지 않음"],
    ["마지막 확인", time(issue.checked_at)],
  ]) {
    const p = node("p", cls);
    p.append(node("span", "field", label), node("span", "", text));
    row.append(p);
  }
  return row;
}
function renderSwitchPanel(d) {
  const card = node("article", `device-card switch-card ${d.status}`);
  card.dataset.deviceId = d.device_id;
  const head = node("div", "device-head"),
    identity = node("div"),
    status = node("div", "panel-status");
  identity.append(
    deviceButton(d),
    node(
      "p",
      "location",
      `${d.management_ip} · ${d.platform} · ${locationText(d)}`,
    ),
  );
  status.append(
    badge(d.status),
    node("span", "panel-time", `확인 ${time(d.checked_at)}`),
  );
  head.append(identity, status);
  card.append(head);
  const layout = FaultPanel.groups(d),
    rack = node("div", "rack");
  rack.setAttribute("aria-label", `${d.hostname} 스위치 포트 패널`);
  if (!d.port_data_current)
    rack.append(
      node(
        "p",
        "rack-warning",
        "? 현재 포트 상태 확인 불가 · 과거 연결 상태는 정상으로 표시하지 않습니다.",
      ),
    );
  for (const group of layout.groups) {
    const module = node("section", "rack-module");
    module.append(slotHeading(d, group.slot, group.label));
    const banks = node("div", "rack-banks");
    for (const bank of group.banks) {
      const bankNode = node("div", "rack-bank"),
        grid = node("div", "socket-grid");
      grid.style.setProperty("--socket-columns", bank.columns);
      for (const item of bank.ports) {
        const view = item.view,
          button = node(
            "button",
            `socket ${view.state}${view.roles.length ? " monitored" : ""}`,
          );
        button.dataset.interface = view.name;
        button.style.gridColumn =
          Math.floor((item.number - bank.start) / 2) + 1;
        button.style.gridRow = item.number % 2 ? 1 : 2;
        const accessible = `${d.hostname} · ${view.name} · ${view.roles.join(" · ")} ${view.label}`;
        button.setAttribute("aria-label", accessible);
        button.title = `${accessible}${item.port.speed ? " · " + item.port.speed : ""}${view.metric ? " · " + view.metric.label : ""} · 선택하여 상세 보기`;
        const number = node("span", "socket-number", item.number);
        if (view.roles.includes("업링크")) number.append(uplinkArrow());
        if (view.roles.includes("중요")) number.append(node("span", "port-role", "★"));
        button.append(number, portSymbol());
        markRecentConnection(button, d, item.port);
        button.onclick = () => openDevice(d.device_id, view.name);
        grid.append(button);
      }
      bankNode.append(
        grid,
        node("div", "bank-caption", `${bank.start}–${bank.end}`),
      );
      banks.append(bankNode);
    }
    module.append(banks);
    rack.append(module);
  }
  if (!layout.groups.length)
    rack.append(
      node(
        "p",
        "rack-warning",
        "물리 포트 수집 정보 없음 · 포트 수와 상태를 확인할 수 없습니다.",
      ),
    );
  card.append(rack);
  const targets = node("div", "panel-targets");
  for (const [kind, label, setting] of [
    ["uplink", "업링크", "uplinks"],
    ["important", "★ 중요 포트", "important_ports"],
  ]) {
    const line = node("div", "target-line");
    if (kind === "uplink") line.append(uplinkArrow());
    line.append(node("strong", "", label));
    const entries = d.port_states.filter((p) => p.kind === kind);
    if (!entries.length)
      line.append(
        node(
          "span",
          "muted",
          d.config[setting] == null ? "지정 필요" : "대상 없음",
        ),
      );
    for (const p of entries) {
      const view = FaultPanel.portView(
        d,
        (d.panel_ports || []).find(
          (port) =>
            FaultPanel.shortName(port.interface) ===
            FaultPanel.shortName(p.interface),
        ) || { interface: p.interface },
      );
      const target = node(
        "button",
        `target-chip ${view.state}`,
        `${p.interface} · ${view.icon} ${view.label}`,
      );
      target.onclick = () => openDevice(d.device_id, p.interface);
      line.append(target);
    }
    targets.append(line);
  }
  card.append(targets);
  const incidents = d.issues.filter(
    (i) => !["configuration", "freshness"].includes(i.kind),
  );
  card.append(...incidents.map(issueElement));
  const footer = node("div", "panel-footer");
  footer.append(
    node(
      "span",
      "",
      d.configuration_missing.length
        ? `? ${d.configuration_missing.join(" · ")} 미설정`
        : "✓ 감시 범위 설정 완료",
    ),
  );
  footer.append(
    node(
      "span",
      "",
      `포트 선택 → 상세 · ${layout.auxiliary ? "논리/관리 인터페이스 " + layout.auxiliary + "개는 상세에서 확인 · " : ""}논리 번호 배열`,
    ),
  );
  card.append(footer);
  return card;
}
function uplinkArrow() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 16 20");
  svg.setAttribute("class", "uplink-arrow");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", "M8 0 0 9h5v11h6V9h5Z");
  svg.append(path);
  return svg;
}
function portSymbol() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 32 28");
  svg.setAttribute("class", "socket-icon");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  for (const [className, path] of [
    ["port-outline", "M7 4h18a2 2 0 0 1 2 2v11h-5v6H10v-6H5V6a2 2 0 0 1 2-2Z"],
    ["port-pins", "M11 8v5m3-5v5m4-5v5m3-5v5"],
  ]) {
    const element = document.createElementNS(ns, "path");
    element.setAttribute("class", className);
    element.setAttribute("d", path);
    svg.append(element);
  }
  return svg;
}
function renderDashboard(data) {
  const focusDevice =
    document.activeElement?.closest(".switch-card")?.dataset.deviceId;
  const focusPort = document.activeElement?.dataset.interface;
  const focusSlot = document.activeElement?.dataset.slot;
  dashboard = data;
  $("#metrics").replaceChildren(
    ...[
      ["중대 장애 장비 수", "critical_devices"],
      ["업링크 장애 수", "uplink_faults"],
      ["장비 작동 불능 수", "device_unreachable"],
      ["중요 포트 장애 수", "important_faults"],
      ["상태 확인 불가 수", "unknown_devices"],
      ["마지막 확인 시각", "last_checked", "time"],
    ].map(([label, key, type]) => metric(label, data.metrics[key], type, key)),
  );
  $("#runtimeState").textContent = data.reference_only
    ? "참고 데이터 · 실시간 확인 불가"
    : data.scheduler.enabled
      ? "● 자동 감시 중"
      : "자동 수집 중지";
  $("#coverage").textContent =
    `전체 ${data.total_devices}대 중 정상 ${data.normal_devices}대 · 확인 필요 ${data.total_devices - data.normal_devices}대`;
  const missing = data.devices.filter(
    (d) => d.configuration_missing.length,
  ).length;
  const allNormal =
    data.total_devices > 0 && data.normal_devices === data.total_devices;
  $("#scopeNotice").className = `notice ${allNormal ? "good" : ""}`;
  $("#scopeNotice").textContent = allNormal
    ? "✓ 설정된 감시 대상 전체가 정상입니다. 미사용 포트는 장애 집계에서 제외합니다."
    : missing
      ? `${missing}대의 위치 또는 감시 대상 설정이 미완료입니다. 지정된 포트만 감시하며, 미설정 항목과 오래된 수집값은 정상으로 표시하지 않습니다.`
      : "장비 작동 불능은 관리 통신 불가를 뜻합니다. 전원 공급 중단 여부는 현재 데이터로 확인할 수 없습니다.";
  const groups = new Map();
  for (const d of data.devices) {
    const b = d.building || "건물 미설정";
    if (!groups.has(b)) groups.set(b, new Map());
    const floors = groups.get(b),
      f = d.floor || "층 미설정";
    if (!floors.has(f)) floors.set(f, []);
    floors.get(f).push(d);
  }
  const priority = (devices) =>
    Math.min(
      ...devices.map((d) => ({ critical: 0, unknown: 1, normal: 2 })[d.status]),
    );
  const buildings = [...groups.entries()].sort(
    (a, b) =>
      priority([...a[1].values()].flat()) - priority([...b[1].values()].flat()),
  );
  const root = $("#buildings");
  root.replaceChildren();
  const select = $("#floorFilter"),
    options = [node("option", "", "전체 층 · 모든 장비")];
  options[0].value = "";
  for (const [name, floors] of buildings) {
    for (const [floor, devices] of [...floors.entries()].sort(
      (a, b) => FaultPanel.floorOrder(a[0]) - FaultPanel.floorOrder(b[0]),
    )) {
      const option = node(
        "option",
        "",
        `${name} / ${floorLabel(floor)} · ${devices.length}대`,
      );
      option.value = JSON.stringify([name, floor]);
      options.push(option);
    }
  }
  if (!options.some((o) => o.value === floorFilter)) floorFilter = "";
  select.replaceChildren(...options);
  select.value = floorFilter;
  $("#portLegend").replaceChildren(
    ...Object.entries(FaultPanel.states).map(([state, spec]) => {
      const label = node("span", `legend-item ${state}`);
      label.append(
        node("i", "legend-dot"),
        node("span", "", `${spec.icon} ${spec.label}`),
      );
      return label;
    }),
    uplinkArrow(),
    node("span", "role-legend", "업링크 · ★ 중요"),
    (() => {
      const legend = node("span", "connection-legend");
      legend.append(node("span", "connection-marker connection-marker-new", "NEW"), " 청록 테두리 · 물리 연결 확인(24시간)");
      return legend;
    })(),
  );
  renderRecentConnections(data);
  for (const [name, floors] of buildings) {
    if (floorFilter && JSON.parse(floorFilter)[0] !== name) continue;
    const building = node("section", "building"),
      head = node("div", "building-header");
    head.append(
      node("h2", "", `▤ ${name}`),
      node(
        "span",
        "",
        floorFilter
          ? `${floors.get(JSON.parse(floorFilter)[1]).length}대 표시 / 전체 ${[...floors.values()].flat().length}대`
          : `${[...floors.values()].flat().length}대 감시`,
      ),
    );
    building.append(head);
    for (const [floor, devices] of [...floors.entries()].sort(
      (a, b) =>
        priority(a[1]) - priority(b[1]) ||
        FaultPanel.floorOrder(a[0]) - FaultPanel.floorOrder(b[0]) ||
        a[0].localeCompare(b[0], "ko", { numeric: true }),
    )) {
      if (floorFilter && JSON.parse(floorFilter)[1] !== floor) continue;
      const section = node("section", "floor"),
        title = node("div", "floor-title", floorLabel(floor));
      title.append(node("small", "", `${devices.length}대`));
      section.append(title);
      for (const d of [...devices].sort(
        (a, b) => priority([a]) - priority([b]),
      ))
        section.append(renderSwitchPanel(d));
      building.append(section);
    }
    root.append(building);
  }
  if (!data.total_devices)
    root.append(node("div", "empty", "등록된 감시 장비가 없습니다."));
  if (focusDevice) {
    const card = [...root.querySelectorAll(".switch-card")].find(
      (e) => e.dataset.deviceId === focusDevice,
    );
    const target = focusPort
      ? [...(card?.querySelectorAll(".socket") || [])].find(
          (e) => e.dataset.interface === focusPort,
        )
      : focusSlot
        ? [...(card?.querySelectorAll(".module-edit") || [])].find(
            (e) => e.dataset.slot === focusSlot,
          )
        : card?.querySelector(".device-link");
    target?.focus({ preventScroll: true });
  }
  $("#collectionStatus").textContent =
    `화면 15초마다 갱신 · 수집 완료 후 ${data.settings.interval_seconds}초 간격 · 연속 ${data.settings.failure_threshold}회 실패 시 장애 확정 · ${data.settings.recovery_threshold}회 정상 시 복구 · ${data.settings.stale_after_seconds}초 초과 시 확인 불가${data.scheduler.error ? " · " + data.scheduler.error : ""}`;
}
async function refresh() {
  if (fetchInFlight) return;
  fetchInFlight = true;
  try {
    renderDashboard(await api("/fault-monitor"));
    $("#connectionError").hidden = true;
    await refreshDetail();
  } catch (error) {
    $("#connectionError").hidden = false;
    $("#connectionError").textContent =
      "감시 서버에 연결할 수 없습니다. 현재 상태 확인 불가 · " + error.message;
    $("#runtimeState").textContent = "서버 연결 끊김";
    $("#recentConnectionList").replaceChildren(node("p", "notice error", "서버 연결을 복구하면 최근 연결 이력을 다시 확인합니다."));
    $("#metrics")
      .querySelectorAll(".metric-value")
      .forEach((n) => (n.textContent = "확인 불가"));
    $("#buildings").replaceChildren(
      node("div", "empty", "서버 연결을 복구하면 감시 현황을 다시 표시합니다."),
    );
    $("#coverage").textContent = "현재 정상 여부를 확인할 수 없습니다.";
    $("#scopeNotice").textContent =
      "마지막 화면의 정상 상태를 현재 상태로 판단하지 마세요.";
    if ($("#deviceDialog").open && !$("#changeDialog").open) {
      $("#detailBody").replaceChildren(
        node(
          "p",
          "notice error",
          "감시 서버 연결이 끊겨 상세 상태도 확인할 수 없습니다.",
        ),
      );
      selectedPort = null;
    }
  } finally {
    fetchInFlight = false;
  }
}
async function refreshDetail() {
  if (!selectedDevice || !$("#deviceDialog").open || $("#changeDialog").open || $("#slotAliasDialog").open)
    return;
  const id = selectedDevice.device_id,
    generation = detailGeneration;
  try {
    const d = await api(`/fault-monitor/devices/${encodeURIComponent(id)}`);
    if (generation !== detailGeneration || !$("#deviceDialog").open || $("#slotAliasDialog").open) return;
    const open = [...document.querySelectorAll("#detailBody details")].map(
        (e) => e.open,
      ),
      portName = selectedPort?.interface;
    selectedDevice = d;
    renderDetail(d);
    document
      .querySelectorAll("#detailBody details")
      .forEach((e, i) => (e.open = open[i]));
    const port = d.ports.find((p) => p.interface === portName),
      button = [...document.querySelectorAll(".port-tile")].find(
        (e) => e.dataset.port === portName,
      );
    if (port && button) selectPort(port, button);
  } catch (error) {
    $("#detailBody").replaceChildren(
      node("p", "notice error", "상세 상태 확인 불가"),
    );
    $("#detailBody").firstChild.textContent =
      "상세 상태 확인 불가 · " + error.message;
    selectedPort = null;
  }
}
function fact(label, value) {
  const item = node("div", "fact");
  item.append(node("dt", "", label), node("dd", "", value || "미확인"));
  return item;
}
function portTable(title, ports, configured) {
  const section = node("section", "detail-section");
  section.append(node("h3", "", title));
  if (!ports.length) {
    section.append(
      node(
        "p",
        "muted",
        configured
          ? "감시 대상 없음으로 명시 설정됨"
          : "감시 대상 미설정 · 관리자 지정 필요",
      ),
    );
    return section;
  }
  const wrap = node("div", "table-scroll"),
    table = node("table", "port-table"),
    header = node("tr");
  ["포트", "상태", "영향 범위"].forEach((t) =>
    header.append(node("th", "", t)),
  );
  const thead = node("thead");
  thead.append(header);
  table.append(thead);
  const body = node("tbody");
  for (const p of ports) {
    const row = node("tr");
    row.append(node("td", "", p.interface));
    const status = node("td");
    status.append(badge(p.state), node("p", "muted", p.label));
    row.append(status, node("td", "", p.impact));
    body.append(row);
  }
  table.append(body);
  wrap.append(table);
  section.append(wrap);
  return section;
}
async function openDevice(id, interfaceName) {
  const generation = ++detailGeneration;
  selectedPort = null;
  selectedDevice = null;
  $("#deviceTitle").textContent = "장비 상태 확인 중";
  $("#deviceLocation").textContent = "";
  $("#detailBody").replaceChildren(
    node("p", "muted", "상세 정보를 불러오고 있습니다."),
  );
  if (!$("#deviceDialog").open) $("#deviceDialog").showModal();
  try {
    const d = await api(`/fault-monitor/devices/${encodeURIComponent(id)}`);
    if (generation !== detailGeneration) return;
    selectedDevice = d;
    renderDetail(d);
    if (interfaceName) {
      const port = d.ports.find(
        (p) =>
          FaultPanel.shortName(p.interface) ===
          FaultPanel.shortName(interfaceName),
      );
      const button = [
        ...document.querySelectorAll("#detailBody .port-tile"),
      ].find(
        (p) =>
          FaultPanel.shortName(p.dataset.port) ===
          FaultPanel.shortName(interfaceName),
      );
      if (port && button) {
        selectPort(port, button);
        button.closest("details").open = true;
        $("#portSelection").scrollIntoView({ block: "center" });
      } else {
        const missing = node(
          "p",
          "notice",
          `${interfaceName} · 해당 포트가 현재 수집 결과에 없습니다. 상태를 확인할 수 없습니다.`,
        );
        $("#detailBody").prepend(missing);
      }
    }
  } catch (error) {
    if (generation === detailGeneration)
      $("#detailBody").replaceChildren(
        node("p", "notice error", error.message),
      );
  }
}
function renderDetail(d) {
  $("#deviceTitle").textContent = d.hostname;
  $("#deviceLocation").textContent = locationText(d);
  const body = $("#detailBody");
  body.replaceChildren();
  const facts = node("dl", "facts");
  facts.append(
    fact("관리 IP", d.management_ip),
    fact("감시 상태", LABELS[d.status]),
    fact("건물 · 층", locationText(d)),
    fact("마지막 정상 확인", time(d.last_healthy_at)),
    fact("마지막 수집 성공", time(d.last_success_at)),
    fact("마지막 확인", time(d.checked_at)),
  );
  body.append(facts);
  if (!d.port_data_current)
    body.append(
      node(
        "p",
        "notice",
        "현재 상태 확인 불가: 아래 포트 정보는 과거 수집값입니다.",
      ),
    );
  if (d.configuration_missing.length)
    body.append(
      node(
        "p",
        "notice",
        `${d.configuration_missing.join(", ")} 미설정 · 감시 범위를 확정해야 전체 정상 여부를 판단할 수 있습니다.`,
      ),
    );
  body.append(
    portTable(
      "업링크 상태",
      d.port_states.filter((p) => p.kind === "uplink"),
      d.config.uplinks !== null && d.config.uplinks !== undefined,
    ),
    portTable(
      "중요 감시 포트",
      d.port_states.filter((p) => p.kind === "important"),
      d.config.important_ports !== null &&
        d.config.important_ports !== undefined,
    ),
  );
  body.append(
    node(
      "p",
      "muted",
      "전원 센서 데이터가 없어 전원 장애를 판정하지 않습니다. 미사용 포트의 링크 끊김은 장애 집계에서 제외합니다.",
    ),
  );
  const layout = node("details", "port-disclosure");
  layout.append(
    node("summary", "", "전체 포트 배치도 · 필요한 경우 펼쳐 보기"),
  );
  layout.append(
    node(
      "p",
      "muted",
      d.device_id === "cisco-backbone"
        ? "확인된 섀시 모듈 기준 · 포트를 선택하면 상태를 확인합니다."
        : "논리 포트 번호 기준 · 실제 전면 배치는 확인되지 않았습니다.",
    ),
  );
  const physicalGroups = FaultPanel.groups(d).groups;
  const auxiliary = d.ports.filter((p) => !FaultPanel.physical(p.interface, d));
  const groups = physicalGroups.map((group) => ({
    ...group, members: group.ports.map((item) => item.port),
  }));
  if (auxiliary.length) groups.push({ label: "기타 인터페이스", members: auxiliary });
  for (const group of groups) {
    layout.append(group.slot
      ? slotHeading(d, group.slot, group.label, "h3")
      : node("h3", "module-label", group.label));
    const grid = node("div", "port-grid");
    for (const p of group.members) {
      const m = d.port_states.find((s) => s.interface === p.interface);
      const status = !d.port_data_current
        ? "unknown"
        : m?.state ||
          (["connected", "up"].includes(p.status) ? "normal" : "maintenance");
      const view = FaultPanel.portView(d, p);
      const button = node("button", `port-tile ${view.state === "slow" ? "slow" : status}`, p.interface);
      if (view.roles.includes("uplink") || view.roles.includes("업링크")) button.append(uplinkArrow());
      button.dataset.port = p.interface;
      const label = view.state === "slow" ? view.label : !d.port_data_current
        ? "미확인"
        : m
          ? LABELS[status]
          : ["connected", "up"].includes(p.status)
            ? "연결"
            : p.status === "disabled"
              ? "비활성"
              : "미감시";
      button.setAttribute("aria-label", `${p.interface} · ${label}`);
      button.title = `${p.interface} · ${label} · ${p.speed || "속도 미확인"}`;
      markRecentConnection(button, d, p);
      button.onclick = () => selectPort(p, button);
      grid.append(button);
    }
    layout.append(grid);
  }
  body.append(layout);
  const selected = node("div", "selection");
  selected.id = "portSelection";
  selected.hidden = true;
  body.append(selected);
  const management = node("details", "management");
  management.append(node("summary", "", "관리 영역 · 포트 차단 / 복구"));
  management.append(
    node(
      "p",
      "muted",
      "배치도에서 포트를 선택하세요. 업링크·백본·이웃 연결 포트는 보호됩니다.",
    ),
  );
  const hint = node(
    "p",
    "muted",
    d.change_capabilities.enabled
      ? "승인 코드와 명령 미리보기 후 실행할 수 있습니다."
      : "이 서버에서는 포트 변경이 비활성화되어 있습니다.",
  );
  hint.id = "protectionHint";
  management.append(hint);
  const actions = node("div", "action-row");
  for (const [text, desired] of [
    ["포트 차단", "shutdown"],
    ["포트 복구", "no shutdown"],
  ]) {
    const b = node(
      "button",
      desired === "shutdown" ? "danger-button" : "",
      text,
    );
    b.id = desired === "shutdown" ? "shutdownPort" : "restorePort";
    b.disabled = true;
    b.onclick = () => prepareChange(desired);
    actions.append(b);
  }
  management.append(actions);
  body.append(management);
  const history = node("details", "port-disclosure");
  history.append(node("summary", "", `장애 · 복구 이력 (${d.history.length})`));
  for (const h of d.history) {
    history.append(
      node(
        "div",
        "history-item",
        `${h.interface || "장비 통신"} · 최초 ${time(h.first_seen)} · 확정 ${time(h.confirmed_at)} · ${h.recovered_at ? "복구 " + time(h.recovered_at) : h.ended_reason || "미복구 (현재 상태는 상단 참조)"}`,
      ),
    );
  }
  if (!d.history.length)
    history.append(node("p", "muted", "아직 확정된 장애 이력이 없습니다."));
  body.append(history);
}
function selectPort(port, button) {
  selectedPort = port;
  document
    .querySelectorAll(".port-tile.selected")
    .forEach((p) => p.classList.remove("selected"));
  button.classList.add("selected");
  const box = $("#portSelection");
  box.hidden = false;
  box.replaceChildren(
    node("h3", "", `${port.interface} 포트`),
    node(
      "p",
      "",
      `${!selectedDevice.port_data_current ? "과거 수집 상태" : "수집 상태"}: ${portStatus(port.status)} · ${port.speed || "속도 미확인"} · VLAN ${port.vlan || "미확인"}`,
    ),
  );
  box.append(
    node(
      "p",
      "muted",
      `연결 IP: ${(port.endpoint_ips || []).join(", ") || "수집 정보 없음"}`,
    ),
  );
  for (const mac of port.endpoint_macs || [])
    box.append(node("code", "mac", mac));
  const connectionHistory = node("section", "connection-history");
  connectionHistory.append(node("p", "muted", "연결 이력 확인 중…"));
  box.append(connectionHistory);
  loadConnectionHistory(selectedDevice.device_id, port.interface, connectionHistory);
  const disabled = ["disabled", "administratively down", "admin-down"].includes(
    port.status,
  );
  const blocked =
    port.protection_reason ||
    (!selectedDevice.port_data_current
      ? "최근 수집이 없어 현재 포트 상태를 확인할 수 없습니다."
      : null) ||
    (["trunk", "routed"].includes(port.vlan)
      ? "트렁크·라우팅 포트는 보호됩니다."
      : null) ||
    (port.neighbor_name || port.neighbor_ip
      ? "이웃 연결 포트는 보호됩니다."
      : null) ||
    (String(port.status).includes("err")
      ? "오류로 비활성화된 포트는 먼저 진단해야 합니다."
      : null);
  $("#protectionHint").textContent =
    blocked ||
    "승인 코드로 변경을 승인하세요. 실행 전후 상태를 다시 확인합니다.";
  $("#shutdownPort").disabled =
    !!blocked || !selectedDevice.change_capabilities.enabled || disabled;
  $("#restorePort").disabled =
    !!blocked || !selectedDevice.change_capabilities.enabled || !disabled;
}
async function prepareChange(desired) {
  const device = selectedDevice,
    port = selectedPort;
  if (!device || !port) return;
  proposal = null;
  $("#approvalCode").value = "";
  $("#changeCommands").textContent = "";
  $("#rollbackCommands").textContent = "";
  $("#executeChange").disabled = true;
  $("#changeResult").textContent = "변경 계획을 확인하고 있습니다.";
  $("#changeTarget").textContent =
    `${device.hostname} · ${device.management_ip} · ${port.interface} · ${desired === "shutdown" ? "차단" : "복구"}`;
  $("#changeDialog").showModal();
  try {
    proposal = await post(
      `/devices/${encodeURIComponent(device.device_id)}/port-admin-state/proposals`,
      { interface: port.interface, desired_state: desired },
    );
    $("#changeCommands").textContent = proposal.commands.join("\n");
    $("#rollbackCommands").textContent = proposal.rollback_commands.join("\n");
    $("#changeResult").textContent =
      `계획 유효 시각: ${time(proposal.expires_at)}`;
    $("#executeChange").disabled = false;
  } catch (error) {
    $("#changeResult").textContent = error.message;
  }
}
$("#changeForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!proposal) return;
  const current = proposal;
  proposal = null;
  $("#executeChange").disabled = true;
  $("#closeChange").disabled = true;
  $("#changeResult").textContent = "사전 확인 → 명령 실행 → 결과 확인 중…";
  const approval = $("#approvalCode").value;
  $("#approvalCode").value = "";
  try {
    const result = await post(
      `/changes/${encodeURIComponent(current.proposal_id)}/execute`,
      { approval_token: approval },
    );
    $("#changeResult").textContent =
      `✓ ${result.interface} · ${portStatus(result.verified_status)} 확인 완료. 시작 설정에는 저장하지 않았습니다.`;
    await refresh();
    if (selectedDevice) await openDevice(selectedDevice.device_id);
  } catch (error) {
    $("#changeResult").textContent =
      `실행 확인 실패: ${error.message}\n상태가 불확실할 수 있으므로 새로 확인한 뒤 복구 명령을 검토하세요.`;
  } finally {
    $("#closeChange").disabled = false;
  }
});
$("#slotAliasForm").addEventListener("submit", saveSlotAlias);
$("#slotAliasInput").oninput = updateSlotAliasPreview;
$("#clearSlotAlias").onclick = () => {
  $("#slotAliasInput").value = "";
  updateSlotAliasPreview();
  $("#slotAliasInput").focus();
};
for (const id of ["closeSlotAlias", "cancelSlotAlias"])
  $("#" + id).onclick = () => $("#slotAliasDialog").close();
$("#slotAliasDialog").addEventListener("cancel", (event) => {
  if (slotAliasSaving) event.preventDefault();
});
$("#slotAliasDialog").addEventListener("close", () => {
  if (!slotEditor) return;
  const root = $(slotEditor.inDetail ? "#detailBody" : "#buildings");
  [...root.querySelectorAll(".module-edit")].find((button) =>
    button.dataset.deviceId === slotEditor.deviceId && button.dataset.slot === slotEditor.slot
  )?.focus({ preventScroll: true });
  slotEditor = null;
});
$("#closeDetail").onclick = () => {
  ++detailGeneration;
  $("#deviceDialog").close();
};
$("#closeChange").onclick = () => {
  $("#changeDialog").close();
  proposal = null;
  $("#approvalCode").value = "";
};
$("#changeDialog").addEventListener("cancel", (event) => {
  if ($("#closeChange").disabled) event.preventDefault();
});
$("#floorFilter").onchange = (event) => {
  floorFilter = event.target.value;
  if (dashboard) renderDashboard(dashboard);
};
refresh();
setInterval(refresh, 15000);
