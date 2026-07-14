const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const appPath = path.join(__dirname, "..", "src", "network_ai_mvp", "static", "app.js");
const source = fs.readFileSync(appPath, "utf8");
const operationsSource = fs.readFileSync(
  path.join(__dirname, "..", "src", "network_ai_mvp", "static", "operations.html"),
  "utf8",
);

class FakeEventSource {
  addEventListener() {}
  close() {}
}

function responsePayload(url) {
  if (url === "/devices") return [];
  if (url === "/audit-log?limit=100") return { events: [] };
  if (url === "/topology") return { nodes: [], edges: [], summary: {} };
  if (url === "/health") return { status: "ok", mode: "read-only", monitoring_transport: "sse" };
  return {};
}

const context = {
  console,
  AbortController,
  Intl,
  URL,
  Promise,
  setTimeout,
  clearTimeout,
  EventSource: FakeEventSource,
  fetch: async (url) => ({
    ok: true,
    status: 200,
    statusText: "OK",
    text: async () => JSON.stringify(responsePayload(url)),
  }),
  document: {
    body: { dataset: { page: "operations" } },
    hidden: false,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
  },
  window: {
    EventSource: FakeEventSource,
    location: { hash: "" },
    addEventListener: () => {},
    setTimeout,
    clearTimeout,
  },
};
vm.createContext(context);
vm.runInContext(source, context, { filename: appPath });

function evaluate(expression) {
  return vm.runInContext(expression, context);
}

function ports(prefix, start, end, extra = "") {
  return Array.from({ length: end - start + 1 }, (_, index) => ({
    interface: `${prefix}${start + index}`,
    status: "connected",
    vlan: "11",
    speed: "a-1G",
    duplex: "a-full",
    description: extra,
  }));
}

assert.equal(evaluate('normalizePortOperationalStatus("connected")'), "connected");
assert.equal(evaluate('normalizePortOperationalStatus("notconnect")'), "unconnected");
assert.equal(evaluate('normalizePortOperationalStatus("disabled")'), "admin-disabled");
assert.equal(evaluate('normalizePortOperationalStatus("errdisabled")'), "fault");
assert.equal(evaluate("normalizePortOperationalStatus(null)"), "unknown");

context.hpeFixture = ports("Et", 1, 28);
const hpe = evaluate(`
  state.selectedDevice = { vendor: "hpe", platform: "HPE 1920-24G-PoE+" };
  buildPhysicalPortGroups(hpeFixture);
`);
assert.equal(hpe.groups.length, 1);
assert.deepEqual(
  Array.from(hpe.groups[0].banks, (bank) => bank.label),
  ["1-8", "9-16", "17-24", "Additional ports"],
);
assert.equal(hpe.groups[0].banks[3].singleRow, true);
assert.deepEqual(Array.from(hpe.groups[0].banks[3].items, (item) => item.number), [25, 26, 27, 28]);

context.fortyEightPlus = [
  ...ports("Et", 1, 52),
  { interface: "Po10", status: "connected" },
  { interface: "Vl11", status: "connected" },
];
const arista = evaluate(`
  state.selectedDevice = { vendor: "arista", platform: "DCS-7050" };
  buildPhysicalPortGroups(fortyEightPlus);
`);
assert.deepEqual(
  Array.from(arista.groups[0].banks, (bank) => bank.label),
  ["1-12", "13-24", "25-36", "37-48", "Additional ports"],
);
assert.equal(arista.groups[0].banks.flatMap((bank) => bank.items).length, 52);
assert.deepEqual(Array.from(arista.logical, (port) => port.interface), ["Po10", "Vl11"]);

context.moreThanFiftyTwo = ports("Et", 1, 56);
const expanded = evaluate("buildPhysicalPortGroups(moreThanFiftyTwo)");
assert.equal(expanded.groups[0].banks.flatMap((bank) => bank.items).length, 56);
assert.deepEqual(
  Array.from(expanded.groups[0].banks.slice(-2), (bank) => Array.from(bank.items, (item) => item.number)),
  [[49, 50, 51, 52], [53, 54, 55, 56]],
);

context.slotFixture = ports("Gi3/", 1, 24);
const cisco = evaluate(`
  state.selectedDevice = { vendor: "cisco", platform: "WS-C4503-E" };
  buildPhysicalPortGroups(slotFixture);
`);
assert.equal(cisco.groups[0].key, "Gi:3");
assert.deepEqual(Array.from(cisco.groups[0].banks, (bank) => bank.label), ["1-12", "13-24"]);

context.warningPort = {
  interface: "Et7",
  status: "connected",
  vlan: "11",
  speed: "a-1G",
  duplex: "a-full",
  description: "Outpatient terminal",
  fcs_errors: 12,
};
assert.equal(evaluate("portHealthSeverity(warningPort)"), "warning");
assert.equal(evaluate("normalizePortOperationalStatus(warningPort.status)"), "connected");
assert.equal(evaluate(`
  state.portStatusFilter = "up";
  state.portModeFilter = "all";
  state.portVlanFilter = "";
  state.portSearchQuery = "";
  portMatchesFilters(warningPort);
`), true);
assert.equal(evaluate(`state.portStatusFilter = "error"; portMatchesFilters(warningPort);`), true);
assert.equal(evaluate("buildPortAriaLabel(warningPort).includes('PoE')"), false);
assert.equal(evaluate("buildPortAriaLabel(warningPort).includes('diagnostic warning')"), true);
const filteredFaceplate = evaluate("buildPhysicalPortGroups(fortyEightPlus)");
assert.equal(filteredFaceplate.groups[0].banks.flatMap((bank) => bank.items).length, 52);

context.summaryFixture = [
  ...ports("Et", 1, 2),
  { interface: "Et3", status: "notconnect", vlan: "trunk", fcs_errors: 4 },
  { interface: "Po10", status: "connected", vlan: "trunk", fcs_errors: 9 },
  { interface: "Vl11", status: "connected" },
];
const summary = evaluate("summarizePhysicalPorts(summaryFixture)");
assert.deepEqual(
  Object.fromEntries(Object.entries(summary)),
  { total: 3, up: 2, down: 1, error: 1, disabled: 0, trunk: 1, logical: 2 },
);

assert.equal(evaluate(`
  state.selectedDevice = { device_id: "arista-1" };
  state.portRefreshPeriod = 0;
  portAutoRefreshEnabled();
`), false);
assert.equal(evaluate(`state.portRefreshPeriod = 30000; portAutoRefreshEnabled();`), true);

const portMatrixOrder = [
  'id="portMatrix"',
  'id="portMatrixSummary"',
  'id="portRefreshPeriod"',
  'class="port-matrix-divider"',
  'id="portStatusLegend"',
  'class="filter-bar"',
  'class="port-table-details"',
].map((marker) => operationsSource.indexOf(marker));
assert.equal(portMatrixOrder.every((position) => position >= 0), true);
assert.deepEqual(portMatrixOrder, portMatrixOrder.slice().sort((left, right) => left - right));
assert.match(source, /document\.addEventListener\("visibilitychange"/);
assert.match(source, /window\.addEventListener\("pagehide"/);
assert.match(source, /\/devices\/\$\{encodeURIComponent\(deviceId\)\}\/ports\/latest/);

console.log("switch panel layout tests passed");
