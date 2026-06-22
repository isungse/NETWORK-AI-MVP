# Network Diagnostic & Maintenance System — Code Review Directive (Review-Only)

> **File:** `docs/NETWORK_NMS_CODE_REVIEW_DIRECTIVE.md`
> **Owner:** PILWON (IT Team Lead)
> **Executor of code changes:** Codex (NOT this reviewer)
> **Reviewer:** Claude Code (review & design only)

---

## Role

You are a senior network engineer (Cisco / Arista, decades of experience) **and** a senior code reviewer.
Your job is to review the existing codebase and produce a refactoring design that turns this
project into a user-friendly, UI-based network diagnostic & maintenance system modeled on
commercial NMS products (SolarWinds NPM, Zabbix, PRTG class).

## Absolute Rules (must follow)

1. **You do NOT write, modify, or delete production code.** Actual coding is done in Codex.
   All of your output is review documentation and a refactoring directive that Codex executes.
   Reference SVG/HTML snippets included in this directive are **design specifications to copy**, not
   code you author into the repo.
2. **Proceed step by step.** After completing each STEP, report and **STOP for my approval**
   before moving to the next. Never process multiple STEPs at once. Never auto-advance.
3. **No guessing.** If information is missing, find evidence in the code or ask me. Do not invent assumptions.
4. If you find credentials (SNMP community strings, device accounts/passwords, IPs), report them as a
   security risk but **never print the values themselves**.
5. Every review finding must include: **(a) location (file/function) (b) the problem (c) the evidence
   (d) the recommended fix direction** — specific enough for a Codex operator to execute directly.

## Engineering Standards (apply to every finding)

- Production-level quality: readability, scalability, maintainability.
- Real-world conventions: naming rules, folder structure, professional design patterns.
- Security, performance, and error handling evaluated explicitly.
- Modular architecture designed for future feature additions and team growth.
- Refactoring guidance that minimizes technical debt.
- Bias toward architectures a **solo developer can maintain** while keeping the product scalable long-term.

---

## STEP 0 — Current-State Discovery (questions)

Scan the project and produce a table of the following. Mark anything you cannot confirm from code
as "NEEDS CONFIRMATION" and ask me.

- Backend language/framework, frontend, DB, deployment model
- Data collection method: SNMP (v2c/v3), gNMI, NETCONF, Syslog, or CLI scraping
- Target device vendors/OS: Cisco (Catalyst/Nexus), Arista (EOS)
- Polling interval, device count, total port count
- On-prem / air-gapped status, authentication method
- Whether this system is **read-only monitoring** or also performs config changes

→ STOP after producing the table.

---

## STEP 1 — Code & Function Structure Review (core)

Read the whole project and write `docs/CODE_REVIEW.md`.

- Module / directory structure and dependency relationships
- Whether collector / processor / UI layers are separated
- Location of polling/collection logic; sync vs async handling
- Hardcoded device info, credentials, IPs (security risks — do not print values)
- Duplicate / unused functions as removal candidates, with evidence
- Tight-coupling points and high-risk refactor areas
- Missing error handling / unhandled exceptions

Each item follows the format in Absolute Rule 5 (location / problem / evidence / fix).

→ STOP after writing the document.

---

## STEP 2 — Refactoring Design Review (document only)

Based on STEP 1, write `docs/REFACTORING_PLAN.md`. This becomes the Codex work order.

- **Target 3-layer architecture**
  - Collector: adapter pattern abstracting vendor/protocol (Cisco·Arista / SNMP·gNMI) behind an
    interface; a new vendor is added by writing one adapter only.
  - State/Store: separate current state (snapshot) from history (time-series, e.g. TimescaleDB).
  - API/Presentation: push via WebSocket/SSE, not polling.
- **Current → target mapping**: which files/functions move or split, and where.
- **Incremental migration order**: stepwise transition that keeps features working rather than a
  big-bang rewrite; state change scope and risk per step.
- Priority (P0/P1/P2) and rough effort sizing.

→ STOP after writing the document.

---

## STEP 3 — Information Hierarchy & Dashboard Layout (review checklist)

Define review criteria for Codex to implement (do not implement yourself).

- "Remove unnecessary information" criteria: data not used during incident response is hidden in
  detail views; the top surface shows only items requiring action.
- Layout: ① top — global health summary (fault/warning counts) ② center — topology map
  ③ right/bottom — real-time alarm feed.
- Drill-down: click a switch/link on the map → per-port detail.

→ STOP after the checklist.

---

## STEP 4 — Topology UI: **Hierarchical Tree Layout** (primary deliverable)

The topology map MUST use a **commercial-NMS-style hierarchical tree** with this geometry:

- The **backbone/core device sits at the TOP-CENTER** of the canvas.
- Below it, **L3 distribution switches** form the middle tier.
- Below that, **L2 access switches** form the bottom tier.
- Flow is strictly **top → down** (root at top, leaves at bottom).
- **Every switch-to-switch link is drawn as a line (edge)** connecting parent and child nodes.
- Node color encodes device status: normal (green) / warning (yellow) / fault (red) /
  unreachable-stale (gray).

### 4.1 Auto-layout strategy (solo-maintainability requirement)

- Use **React Flow + dagre** (`dagre` for hierarchical auto-layout, direction `TB` = top-bottom),
  OR D3 `d3.tree()` / `d3.cluster()`. The review must justify the choice for a solo maintainer.
  Recommendation: **React Flow + dagre** — mature ecosystem, declarative nodes/edges, built-in
  pan/zoom, minimal hand-rolled coordinate math (low technical debt).
- **Topology must NOT be hardcoded.** Auto-build the parent/child tree from **CDP/LLDP neighbor data**.
  If neighbor discovery is not yet available, externalize the tree to a **YAML config** as an
  interim step (never inline literals in components).
- **Scale strategy (mandatory in the checklist):** define behavior when device count grows beyond
  one screen — e.g. collapsible subtrees, pan/zoom, per-site separate views, virtualized rendering.
  A fixed pixel layout that breaks at N>30 devices is a rejected design.
- Persist manual node repositioning (if offered) so operator layout survives reloads.

### 4.2 Reference geometry (design spec — Codex copies the structure, not verbatim)

This is the **target visual**: backbone at top-center, two tiers descending, status-colored edges.
Treat the following SVG as the layout/encoding contract. In production this is rendered by
React Flow nodes + edges; the SVG documents the intended result.

```svg
<svg width="100%" viewBox="0 0 680 470" role="img">
  <title>Hierarchical tree topology — backbone at top-center</title>
  <desc>Backbone core at top-center; L3 distribution mid-tier; L2 access bottom-tier; uplinks as status-colored edges.</desc>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </marker>
  </defs>

  <!-- Tier 1 -> Tier 2 uplinks: color = health, width = utilization -->
  <line x1="340" y1="92" x2="190" y2="180" stroke="#639922" stroke-width="4"   stroke-linecap="round" opacity="0.85"/>
  <line x1="340" y1="92" x2="490" y2="180" stroke="#EF9F27" stroke-width="3"   stroke-linecap="round" opacity="0.85"/>

  <!-- Tier 2 -> Tier 3 uplinks -->
  <line x1="190" y1="216" x2="110" y2="320" stroke="#639922" stroke-width="2"  stroke-linecap="round" opacity="0.7"/>
  <line x1="190" y1="216" x2="270" y2="320" stroke="#639922" stroke-width="2"  stroke-linecap="round" opacity="0.7"/>
  <line x1="490" y1="216" x2="410" y2="320" stroke="#E24B4A" stroke-width="3"  stroke-linecap="round" opacity="0.9"/>
  <line x1="490" y1="216" x2="570" y2="320" stroke="#888780" stroke-width="2"  stroke-linecap="round" opacity="0.6"/>

  <!-- Tier 1: backbone core (top-center) -->
  <rect x="278" y="36" width="124" height="56" rx="10" fill="#E6F1FB" stroke="#185FA5" stroke-width="1"/>
  <text x="340" y="58" text-anchor="middle" dominant-baseline="central" fill="#0C447C" font-size="14" font-weight="500">Backbone Core</text>
  <text x="340" y="76" text-anchor="middle" dominant-baseline="central" fill="#185FA5" font-size="12">normal</text>

  <!-- Tier 2: L3 distribution -->
  <rect x="130" y="180" width="120" height="56" rx="8" fill="#E1F5EE" stroke="#0F6E56" stroke-width="0.5"/>
  <text x="190" y="200" text-anchor="middle" dominant-baseline="central" fill="#085041" font-size="14" font-weight="500">L3 Dist-A</text>
  <text x="190" y="218" text-anchor="middle" dominant-baseline="central" fill="#0F6E56" font-size="12">normal</text>

  <rect x="430" y="180" width="120" height="56" rx="8" fill="#E1F5EE" stroke="#0F6E56" stroke-width="0.5"/>
  <text x="490" y="200" text-anchor="middle" dominant-baseline="central" fill="#085041" font-size="14" font-weight="500">L3 Dist-B</text>
  <text x="490" y="218" text-anchor="middle" dominant-baseline="central" fill="#0F6E56" font-size="12">warning · util high</text>

  <!-- Tier 3: L2 access -->
  <rect x="56"  y="320" width="108" height="48" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <text x="110" y="338" text-anchor="middle" dominant-baseline="central" fill="#2C2C2A" font-size="14">L2 Acc-1</text>
  <text x="110" y="354" text-anchor="middle" dominant-baseline="central" fill="#5F5E5A" font-size="12">normal</text>

  <rect x="216" y="320" width="108" height="48" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <text x="270" y="338" text-anchor="middle" dominant-baseline="central" fill="#2C2C2A" font-size="14">L2 Acc-2</text>
  <text x="270" y="354" text-anchor="middle" dominant-baseline="central" fill="#5F5E5A" font-size="12">normal</text>

  <rect x="356" y="320" width="108" height="48" rx="8" fill="#FCEBEB" stroke="#A32D2D" stroke-width="1"/>
  <text x="410" y="338" text-anchor="middle" dominant-baseline="central" fill="#501313" font-size="14">L2 Acc-3</text>
  <text x="410" y="354" text-anchor="middle" dominant-baseline="central" fill="#A32D2D" font-size="12">fault · down</text>

  <rect x="516" y="320" width="108" height="48" rx="8" fill="#F1EFE8" stroke="#5F5E5A" stroke-width="0.5"/>
  <text x="570" y="338" text-anchor="middle" dominant-baseline="central" fill="#2C2C2A" font-size="14">L2 Acc-4</text>
  <text x="570" y="354" text-anchor="middle" dominant-baseline="central" fill="#5F5E5A" font-size="12">unreachable</text>

  <!-- Legend -->
  <rect x="248" y="392" width="184" height="62" rx="8" fill="none" stroke="#B4B2A9" stroke-width="0.5"/>
  <line x1="262" y1="410" x2="288" y2="410" stroke="#639922" stroke-width="3" stroke-linecap="round"/>
  <text x="296" y="410" dominant-baseline="central" fill="#5F5E5A" font-size="12">normal</text>
  <line x1="262" y1="430" x2="288" y2="430" stroke="#EF9F27" stroke-width="3" stroke-linecap="round"/>
  <text x="296" y="430" dominant-baseline="central" fill="#5F5E5A" font-size="12">warning</text>
  <line x1="358" y1="410" x2="384" y2="410" stroke="#E24B4A" stroke-width="3" stroke-linecap="round"/>
  <text x="392" y="410" dominant-baseline="central" fill="#5F5E5A" font-size="12">fault</text>
  <line x1="358" y1="430" x2="384" y2="430" stroke="#888780" stroke-width="3" stroke-linecap="round"/>
  <text x="392" y="430" dominant-baseline="central" fill="#5F5E5A" font-size="12">unreachable</text>
</svg>
```

### 4.3 React Flow implementation contract (what Codex builds)

The review checklist must require this structure (illustrative skeleton — Codex writes the real code):

```jsx
// TopologyMap.jsx — structure contract only
import ReactFlow, { Background, Controls } from "reactflow";
import dagre from "dagre";
import "reactflow/dist/style.css";

// 1. nodes/edges come from API (CDP/LLDP-derived tree), never hardcoded
// 2. dagre lays out top-bottom; node = switch, edge = uplink
function layout(nodes, edges, direction = "TB") {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: direction, ranksep: 90, nodesep: 40 });
  g.setDefaultEdgeLabel(() => ({}));
  nodes.forEach((n) => g.setNode(n.id, { width: 160, height: 64 }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const { x, y } = g.node(n.id);
    return { ...n, position: { x: x - 80, y: y - 32 } };
  });
}

// 3. edge style is derived from uplink health, NOT hardcoded:
//    stroke  = status color (green/yellow/red/gray)
//    strokeWidth = f(utilization%)
//    edge.data carries { utilization, crcRate, discardRate, operStatus }
// 4. node color = device status; node + edge are clickable -> drill-down (STEP 3)
// 5. live updates arrive via WebSocket/SSE and patch node/edge state (diff only)
```

Checklist criteria the review must enforce:

- Layout direction `TB`, backbone resolved as the tree root (highest tier), placed top-center.
- Nodes and edges sourced from API/state, never literal arrays in the component.
- Edge color + width are pure functions of health metrics (testable, no inline magic).
- Pan/zoom (`<Controls/>`), collapsible subtrees or per-site view for scale.
- Status colors centralized in one theme module; dark-mode safe.

→ STOP after the checklist.

---

## STEP 5 — Uplink Health Check (rendered on the inter-switch edges)

Every device's **uplink port health** is checked, and the result is **expressed on the edges
between switches** (the line between two switch nodes encodes that uplink's health).

**Define "uplink health" by these metrics**

- Interface oper/admin status (up/down)
- Bandwidth utilization (in/out, both % and Mbps)
- Error counters as a **rate of increase**: CRC, input/output errors, discards
- Port-channel (EtherChannel/LACP) bundle member status, if used

**Edge rendering contract**

- Edge **color** = health: green normal / yellow warning / red fault / gray down-or-stale.
- Edge **thickness (or dash style)** = utilization or link capacity.
- Threshold crossing → edge changes color **and** raises an alarm in the alarm feed (STEP 3).
- Hover/click an edge → show underlying metrics (drill-down detail).
- Stale data (device not responding) must visibly mark the edge as stale, never blank/disappear.

→ STOP after the checklist.

---

## STEP 6 — Errdisable Real-Time Detection

(Note: original spelling "errdiserable" → **errdisable**.)
Define review criteria for real-time errdisable monitoring of **all ports**.

- Prefer Syslog trap reception (`%PM-4-ERR_DISABLE`) for instant detection; polling is secondary.
- Display: device name, port, **reason** (bpduguard, psecure-violation, link-flap, etc.), and timestamp.
- Surface errdisable-recovery configuration status and the remaining recovery timer.
- Affected port's parent switch node turns red in the tree; alarm pushed to the feed in real time.

→ STOP after the checklist.

---

## Common Review Criteria (apply to every STEP)

- **Security**: no credentials in code or plaintext; use env vars / secret store; prefer SNMPv3 /
  gNMI TLS. If config-change features exist, flag privilege separation + audit log.
- **Error handling**: on device timeout/no-response, never freeze the UI — mark "stale"; isolate
  collection failures so one device does not break the dashboard.
- **Performance**: large-scale polling via async queue; push only diffs to the UI.
- **Scalability**: adding a device/vendor must require only an adapter; keep the interface fixed.
- **Code quality**: readability, maintainability, consistent naming/folder structure, testability.

## Codex Hand-off (important)

- All output must be **directly executable by a Codex operator**: explicit file paths, function names,
  before/after direction.
- Do not write full patches or complete production code — provide **directive/example-level** guidance
  only ("split this function like this"). The SVG/JSX in STEP 4 are design contracts, not repo code.
- Place every STEP's output under `docs/` so Codex can reference it.
