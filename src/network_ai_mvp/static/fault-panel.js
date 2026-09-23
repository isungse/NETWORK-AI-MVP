"use strict";
// Pure presentation rules shared by the overview and its reproducible checks.
const FaultPanel = (() => {
  const states = {
    critical: { label: "장애", icon: "!" },
    pending: { label: "재확인", icon: "◷" },
    connected: { label: "연결", icon: "✓" },
    idle: { label: "미연결", icon: "−" },
    disabled: { label: "비활성", icon: "Ⅱ" },
    unknown: { label: "미확인", icon: "?" },
    error: { label: "오류", icon: "!" },
  };
  function shortName(value) {
    return String(value || "")
      .replace(/^Ethernet/i, "Et")
      .replace(/^GigabitEthernet/i, "Gi")
      .replace(/^TenGigabitEthernet/i, "Te")
      .replace(/^FastEthernet/i, "Fa");
  }
  function physical(value, device) {
    const name = shortName(value);
    // Standalone FastEthernet management interfaces stay in device details.
    if (name === "Fa0") return null;
    if (device.device_id === "cisco-backbone" && name === "Fa1") return null;
    const match = name.match(/^(Et|Gi|Te|Fa)(\d+(?:\/\d+)*)$/i);
    if (!match) return null;
    const path = match[2].split("/");
    return {
      name,
      number: Number(path.at(-1)),
      prefix: match[1],
      slot: path.slice(0, -1).join("/"),
    };
  }
  function portView(device, port) {
    const name = shortName(port.interface);
    const metrics = device.port_states.filter(
      (p) => shortName(p.interface) === name,
    );
    const metric = [...metrics].sort(
      (a, b) =>
        (({ critical: 0, pending: 1, unknown: 2, maintenance: 3, normal: 4 })[
          a.state
        ] ?? 5) -
        ({ critical: 0, pending: 1, unknown: 2, maintenance: 3, normal: 4 }[
          b.state
        ] ?? 5),
    )[0];
    const status = String(port.status || "").toLowerCase();
    let state = "unknown";
    if (device.port_data_current && status) {
      if (metric && ["critical", "pending", "unknown"].includes(metric.state))
        state = metric.state;
      else if (
        [
          "disabled",
          "administratively down",
          "admin-down",
          "admin down",
        ].includes(status)
      )
        state = "disabled";
      else if (["connected", "up"].includes(status)) state = "connected";
      else if (["down", "notconnect"].includes(status)) state = "idle";
      else if (["errdisabled", "err-disabled"].includes(status))
        state = "error";
    }
    const roles = [];
    if (metrics.some((p) => p.kind === "uplink")) roles.push("업링크");
    if (metrics.some((p) => p.kind === "important")) roles.push("중요");
    return { name, state, ...states[state], roles, metric };
  }
  function groups(device) {
    const ports = [...(device.panel_ports || device.ports || [])];
    const names = new Set(ports.map((p) => shortName(p.interface)));
    // Explicitly configured but missing interfaces remain visible as unknown.
    for (const spec of device.port_states) {
      const name = shortName(spec.interface);
      if (!names.has(name)) {
        ports.push({ interface: name });
        names.add(name);
      }
    }
    const groups = new Map();
    let auxiliary = 0;
    for (const port of ports) {
      const info = physical(port.interface, device);
      if (!info) {
        auxiliary++;
        continue;
      }
      const confirmedModule =
        device.device_id === "cisco-backbone" &&
        device.platform === "WS-C4503-E"
          ? { 1: "WS-X45-SUP7-E", 2: "WS-X4724-SFP-E", 3: "WS-X4748-RJ45-E" }[
              info.slot
            ]
          : null;
      const key = confirmedModule
        ? `slot:${info.slot}`
        : `${info.prefix}:${info.slot}`;
      if (!groups.has(key))
        groups.set(key, {
          key,
          label: confirmedModule
            ? `슬롯 ${info.slot} · ${confirmedModule}`
            : `${info.prefix}${info.slot ? info.slot + "/" : ""} 포트`,
          ports: [],
        });
      groups
        .get(key)
        .ports.push({ ...info, port, view: portView(device, port) });
    }
    const result = [...groups.values()].sort((a, b) =>
      a.key.localeCompare(b.key, "en", { numeric: true }),
    );
    for (const group of result) {
      const banks = new Map();
      for (const item of group.ports.sort((a, b) => a.number - b.number)) {
        const start = Math.floor((item.number - 1) / 12) * 12 + 1;
        if (!banks.has(start)) banks.set(start, { start, ports: [] });
        banks.get(start).ports.push(item);
      }
      group.banks = [...banks.values()];
      for (const bank of group.banks) {
        bank.end = Math.max(...bank.ports.map((p) => p.number));
        bank.columns = Math.ceil((bank.end - bank.start + 1) / 2);
      }
    }
    return { groups: result, auxiliary };
  }
  function floorOrder(value) {
    if (/^B\d+F$/i.test(value)) return -Number(value.slice(1, -1));
    if (/^\d+F$/i.test(value)) return Number(value.slice(0, -1));
    return 999;
  }
  return { states, shortName, physical, portView, groups, floorOrder };
})();
