const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const context = vm.createContext({});
vm.runInContext(
  fs.readFileSync("src/network_ai_mvp/static/fault-panel.js", "utf8"),
  context,
);
const panel = vm.runInContext("FaultPanel", context);
const device = {
  device_id: "test",
  platform: "test",
  port_data_current: true,
  port_states: [],
  panel_ports: [],
};
const port = { interface: "Et1", status: "connected" };
assert.equal(panel.physical("Fa0", device), null);
assert.equal(panel.portView(device, port).state, "connected");
assert.equal(
  panel.portView({ ...device, port_data_current: false }, port).state,
  "unknown",
);
assert.equal(
  panel.portView(device, { ...port, status: "notconnect" }).state,
  "idle",
);
assert.equal(
  panel.portView(device, { ...port, status: "disabled" }).state,
  "disabled",
);
assert.equal(
  panel.portView(device, { ...port, status: null }).state,
  "unknown",
);
for (const kind of ["uplink", "important"]) {
  const monitored = {
    ...device,
    port_states: [{ kind, interface: "Ethernet1", state: "critical" }],
  };
  assert.equal(
    panel.portView(monitored, { ...port, status: "disabled" }).state,
    "critical",
  );
  assert.equal(
    panel.portView(monitored, { ...port, status: "down" }).state,
    "critical",
  );
  assert.equal(
    panel.portView(
      { ...monitored, port_data_current: false },
      { ...port, status: "down" },
    ).state,
    "unknown",
  );
}
const recovery = {
  ...device,
  port_states: [{ kind: "uplink", interface: "Et1", state: "pending" }],
};
assert.equal(panel.portView(recovery, port).state, "pending");
const fixture = {
  ...device,
  panel_ports: [
    ...Array.from({ length: 52 }, (_, i) => ({
      interface: `Et${i + 1}`,
      status: "connected",
    })),
    { interface: "Vl101" },
    { interface: "Ma1" },
  ],
};
const layout = panel.groups(fixture);
assert.equal(layout.groups.length, 1);
assert.equal(layout.groups[0].ports.length, 52);
assert.equal(layout.groups[0].banks.length, 5);
assert.equal(layout.auxiliary, 2);
const missing = panel.groups({
  ...device,
  port_states: [{ kind: "uplink", interface: "Et52", state: "unknown" }],
});
assert.equal(missing.groups[0].ports[0].view.state, "unknown");
assert.equal(missing.groups[0].ports[0].number, 52);
const chassis = panel.groups({
  ...device,
  device_id: "cisco-backbone",
  platform: "WS-C4503-E",
  panel_ports: [
    { interface: "Gi1/1" },
    { interface: "Te1/3" },
    { interface: "Gi3/48" },
    { interface: "Fa1" },
  ],
});
assert.equal(chassis.groups.length, 2);
assert.equal(chassis.groups[0].ports.length, 2);
assert.equal(chassis.auxiliary, 1);
assert.ok(panel.floorOrder("B1F") < panel.floorOrder("1F"));
console.log("Fault panel state, scope, and layout checks passed");

for (const speed of ["10", "a-10", "10M", "a-10M", "10Mbps"]) {
  assert.equal(panel.portView(device, { ...port, speed }).state, "slow");
  assert.equal(panel.portView({ ...device, port_data_current: false }, { ...port, speed }).state, "unknown");
  assert.equal(panel.portView(device, { ...port, status: "notconnect", speed }).state, "idle");
  assert.equal(panel.portView(recovery, { ...port, speed }).state, "pending");
}
for (const speed of ["100", "a-100M", "1G", "10G", "auto", ""]) {
  assert.equal(panel.portView(device, { ...port, speed }).state, "connected");
}

const arista4f = panel.groups({
  ...device, platform: "DCS-7050TX3",
  port_states: [{kind: "uplink", interface: "Et56/1", state: "normal"}],
  panel_ports: [
    ...Array.from({length: 48}, (_, i) => ({interface: `Et${i+1}`, status: "connected"})),
    ...Array.from({length: 8}, (_, i) => ({interface: `Et${i+49}/1`, status: "connected"})),
  ],
});
assert.equal(arista4f.groups.length, 1);
assert.equal(arista4f.groups[0].ports.length, 56);
const uplinkBank = arista4f.groups[0].banks.at(-1);
assert.equal(uplinkBank.start, 49);
assert.equal(uplinkBank.end, 56);
assert.equal(new Set(uplinkBank.ports.map(p => p.number)).size, 8);
assert.equal(uplinkBank.ports.at(-1).view.name, "Et56/1");
assert.ok(uplinkBank.ports.at(-1).view.roles.includes("업링크"));
assert.equal(panel.physical("Gi1/0/28", device).slot, "1/0");

const core = panel.groups({
  ...device, platform: "DCS-7050SX3-48YC8-F",
  port_states: [{kind: "uplink", interface: "Et47", state: "normal"}, {kind: "uplink", interface: "Et48", state: "normal"}],
  panel_ports: [
    ...Array.from({length: 48}, (_, i) => ({interface: `Et${i+1}`, status: "connected"})),
    ...Array.from({length: 8}, (_, i) => ({interface: `Et${i+49}/1`, status: "connected"})),
    {interface: "Ma1"}, {interface: "Po10"}, {interface: "Vl10"},
  ],
});
assert.equal(core.groups.length, 1);
assert.equal(core.groups[0].ports.length, 56);
assert.equal(core.auxiliary, 3);
assert.equal(core.groups[0].banks.at(-1).ports.at(-1).view.name, "Et56/1");
assert.equal(core.groups[0].ports.filter(p => p.view.roles.includes("업링크")).length, 2);
