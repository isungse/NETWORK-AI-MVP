# Topology Tree — Implementation Directive (Build Spec)

> **File:** `docs/TOPOLOGY_TREE_DESIGN_SPEC.md`
> **Executor:** Codex (this is an implementation order — write the actual code)
> **Status:** Code review complete. Implement per this spec.
> **Owner:** PILWON (IT Team Lead)

---

## 0. Scope & Intent

Build the network topology view as a **commercial-NMS-style hierarchical tree**:

- Backbone/core device at **top-center** (tree root).
- L3 distribution switches in the **middle tier**.
- L2 access switches in the **bottom tier**.
- Flow strictly **top → down**.
- Every switch-to-switch link rendered as an **edge** whose **color = uplink health** and
  **thickness = utilization**.
- Node color = device status. Nodes and edges are clickable → drill-down.
- Live state arrives via **WebSocket/SSE** and patches the graph (diff only, no full reload).

**Non-goals (do NOT build here):** the collector layer, alarm-feed panel internals, and per-port
detail drawer are separate modules. This directive covers the topology canvas, its data contract,
and the health→visual encoding only. Integrate via the interfaces in §2.

---

## 1. Tech Stack & Dependencies

- **React 18 + TypeScript** (strict mode on).
- **React Flow** (`reactflow`) for the canvas — pan/zoom/minimap built in, declarative nodes/edges.
- **dagre** (`@dagrejs/dagre`) for hierarchical auto-layout (`rankdir: TB`).
- **State:** Zustand for topology store (lightweight, no boilerplate; fits solo maintenance).
- **Transport:** **SSE** (`EventSource`) for live state push — current backend is server→client only
  (job submit → client polls/streams status). Wrapped behind a `TopologyStream` interface (§7) so the
  transport can be swapped without touching the store or components. WebSocket is deferred until the
  client needs to push upstream (see §12).
- No D3 hand-rolled layout. No inline coordinate math in components.

```bash
npm i reactflow @dagrejs/dagre zustand
```

---

## 2. Data Contract (the integration boundary)

The backend supplies the tree; **the frontend never hardcodes nodes/edges**. Topology is derived
from CDP/LLDP neighbor data on the server. If discovery is not ready, the server reads a YAML config
and serves the same shape — the frontend is agnostic to the source.

```ts
// src/features/topology/types.ts
export type DeviceStatus = "normal" | "warning" | "fault" | "unreachable";
export type DeviceTier = "backbone" | "distribution" | "access";

export interface TopologyNode {
  id: string; // stable device id (e.g. mgmt IP or hostname hash)
  label: string; // display name
  tier: DeviceTier; // drives rank in the tree
  status: DeviceStatus; // drives node color
  model?: string; // e.g. "C9300-48P" / "DCS-7050SX"
}

export interface UplinkMetrics {
  operStatus: "up" | "down";
  adminStatus: "up" | "down";
  utilizationPct: number; // 0..100, max(in,out)
  inMbps: number;
  outMbps: number;
  crcErrRate: number; // delta/sec
  discardRate: number; // delta/sec
  portChannel?: { members: number; up: number };
  stale: boolean; // true when source device not responding
}

export interface TopologyEdge {
  id: string;
  source: string; // parent node id (higher tier)
  target: string; // child node id (lower tier)
  metrics: UplinkMetrics; // drives edge color + width
}

export interface TopologySnapshot {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  generatedAt: string; // ISO timestamp
}

// Live patch pushed over WS/SSE — apply diffs, never full reload
export type TopologyPatch =
  | { type: "node"; id: string; status: DeviceStatus }
  | { type: "edge"; id: string; metrics: Partial<UplinkMetrics> };
```

---

## 3. Folder Structure

```
src/features/topology/
├── types.ts                  // contracts above
├── api/
│   ├── topologyClient.ts      // fetch initial snapshot (REST)
│   ├── TopologyStream.ts      // transport interface (subscribe -> TopologyPatch)
│   └── sseStream.ts           // SSE (EventSource) implementation of TopologyStream
├── store/
│   └── useTopologyStore.ts    // Zustand: nodes, edges, applyPatch()
├── layout/
│   └── treeLayout.ts          // dagre TB auto-layout (pure function)
├── theme/
│   └── healthTheme.ts         // status/utilization -> color & width (pure)
├── nodes/
│   └── SwitchNode.tsx         // custom React Flow node
├── edges/
│   └── UplinkEdge.tsx         // custom edge (color/width from metrics)
├── TopologyMap.tsx            // the canvas, wires everything
└── index.ts
```

Rationale: feature-folder keeps the module self-contained for future extraction/scaling. Pure
functions (`layout`, `theme`) are unit-testable and carry zero React/coupling — low technical debt.

---

## 4. Health → Visual Encoding (single source of truth)

All color/width logic lives in ONE module. No magic values scattered in components.

```ts
// src/features/topology/theme/healthTheme.ts
import type { DeviceStatus, UplinkMetrics } from "../types";

export const STATUS_COLOR: Record<DeviceStatus, string> = {
  normal: "#639922",
  warning: "#EF9F27",
  fault: "#E24B4A",
  unreachable: "#888780",
};

// Edge health is derived from metrics, independent of node status.
export function edgeStatus(m: UplinkMetrics): DeviceStatus {
  if (m.stale || m.operStatus === "down")
    return m.stale ? "unreachable" : "fault";
  if (m.crcErrRate > 0 || m.discardRate > 0) return "warning";
  if (m.utilizationPct >= 80) return "warning";
  return "normal";
}

export function edgeColor(m: UplinkMetrics): string {
  return STATUS_COLOR[edgeStatus(m)];
}

// Thickness encodes utilization: 2px (idle) .. 5px (saturated).
export function edgeWidth(m: UplinkMetrics): number {
  const clamped = Math.max(0, Math.min(100, m.utilizationPct));
  return 2 + (clamped / 100) * 3;
}
```

> Thresholds (80% util, error rate > 0) are placeholders — confirm against operational policy and
> centralize as named constants. Do not inline them.

---

## 5. Auto-Layout (dagre, top-bottom)

```ts
// src/features/topology/layout/treeLayout.ts
import Dagre from "@dagrejs/dagre";
import type { Node, Edge } from "reactflow";

const NODE_W = 160;
const NODE_H = 64;

export function applyTreeLayout(nodes: Node[], edges: Edge[]): Node[] {
  const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", ranksep: 90, nodesep: 40 });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  Dagre.layout(g);

  return nodes.map((n) => {
    const p = g.node(n.id);
    return { ...n, position: { x: p.x - NODE_W / 2, y: p.y - NODE_H / 2 } };
  });
}
```

The backbone (tier `backbone`) has no incoming edges, so dagre ranks it at the top automatically and
centers it across its descendants — that satisfies "top-center root".

---

## 6. Custom Node & Edge

```tsx
// src/features/topology/nodes/SwitchNode.tsx
import { Handle, Position, type NodeProps } from "reactflow";
import { STATUS_COLOR } from "../theme/healthTheme";
import type { TopologyNode } from "../types";

export function SwitchNode({ data }: NodeProps<TopologyNode>) {
  const color = STATUS_COLOR[data.status];
  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`${data.label}, ${data.status}`}
      style={{
        width: 160,
        height: 64,
        borderRadius: 10,
        border: `2px solid ${color}`,
        background: "var(--surface, #fff)",
        display: "grid",
        placeItems: "center",
        cursor: "pointer",
      }}
    >
      <Handle type="target" position={Position.Top} />
      <strong style={{ fontWeight: 500 }}>{data.label}</strong>
      <span style={{ color, fontSize: 12 }}>{data.status}</span>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
```

```tsx
// src/features/topology/edges/UplinkEdge.tsx
import { BaseEdge, getSmoothStepPath, type EdgeProps } from "reactflow";
import { edgeColor, edgeWidth } from "../theme/healthTheme";
import type { UplinkMetrics } from "../types";

export function UplinkEdge(props: EdgeProps<{ metrics: UplinkMetrics }>) {
  const { sourceX, sourceY, targetX, targetY } = props;
  const [path] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY });
  const m = props.data!.metrics;
  return (
    <BaseEdge
      path={path}
      style={{
        stroke: edgeColor(m),
        strokeWidth: edgeWidth(m),
        strokeDasharray: m.stale ? "6 5" : undefined,
      }}
    />
  );
}
```

Stale links render dashed so they read as "no fresh data", never blank/removed.

---

## 7. Store & Live Updates

```ts
// src/features/topology/store/useTopologyStore.ts
import { create } from "zustand";
import type { Node, Edge } from "reactflow";
import type { TopologySnapshot, TopologyPatch } from "../types";
import { applyTreeLayout } from "../layout/treeLayout";

interface State {
  nodes: Node[];
  edges: Edge[];
  hydrate: (snap: TopologySnapshot) => void;
  applyPatch: (p: TopologyPatch) => void;
  markAllStale: () => void; // called by the stream on disconnect
}

export const useTopologyStore = create<State>((set, get) => ({
  nodes: [],
  edges: [],
  hydrate: (snap) => {
    const nodes: Node[] = snap.nodes.map((n) => ({
      id: n.id,
      type: "switch",
      position: { x: 0, y: 0 },
      data: n,
    }));
    const edges: Edge[] = snap.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      type: "uplink",
      data: { metrics: e.metrics },
    }));
    set({ nodes: applyTreeLayout(nodes, edges), edges });
  },
  applyPatch: (p) => {
    if (p.type === "node") {
      set({
        nodes: get().nodes.map((n) =>
          n.id === p.id ? { ...n, data: { ...n.data, status: p.status } } : n,
        ),
      });
    } else {
      set({
        edges: get().edges.map((e) =>
          e.id === p.id
            ? { ...e, data: { metrics: { ...e.data.metrics, ...p.metrics } } }
            : e,
        ),
      });
    }
  },
  markAllStale: () => {
    set({
      edges: get().edges.map((e) => ({
        ...e,
        data: { metrics: { ...e.data.metrics, stale: true } },
      })),
    });
  },
}));
```

Layout runs once on hydrate; patches mutate data only (no re-layout thrash). Re-run layout solely
when topology _structure_ changes (node/edge added/removed), not on metric updates.

### 7.1 Transport interface (swap-ready)

The store depends on an **interface**, not on SSE directly. This is the single seam that lets you
move to WebSocket later (§12) without touching the store or any component.

```ts
// src/features/topology/api/TopologyStream.ts
import type { TopologyPatch } from "../types";

export interface TopologyStream {
  // returns an unsubscribe fn; must auto-reconnect internally
  subscribe(
    onPatch: (p: TopologyPatch) => void,
    onStale: () => void,
  ): () => void;
}
```

### 7.2 SSE implementation (current transport)

```ts
// src/features/topology/api/sseStream.ts
import type { TopologyStream } from "./TopologyStream";
import type { TopologyPatch } from "../types";

const STREAM_URL = "/api/topology/stream"; // server sends `data: <TopologyPatch JSON>`

export function createSseStream(): TopologyStream {
  return {
    subscribe(onPatch, onStale) {
      let es: EventSource | null = null;
      let closed = false;

      const open = () => {
        es = new EventSource(STREAM_URL, { withCredentials: true });
        es.onmessage = (ev) => {
          try {
            onPatch(JSON.parse(ev.data) as TopologyPatch);
          } catch {
            /* drop malformed frame, do not crash the UI */
          }
        };
        es.onerror = () => {
          // EventSource auto-reconnects; until the next open, mark links stale
          onStale();
          // if the server closed permanently, recreate after a short backoff
          if (es && es.readyState === EventSource.CLOSED && !closed) {
            es.close();
            setTimeout(open, 3000);
          }
        };
      };

      open();
      return () => {
        closed = true;
        es?.close();
      };
    },
  };
}
```

EventSource reconnects automatically on transient drops; `onStale()` flips every edge to dashed
(via the store) so the operator sees "data is not fresh" instead of a frozen or blank map.

---

## 8. Canvas

```tsx
// src/features/topology/TopologyMap.tsx
import { useEffect } from "react";
import ReactFlow, { Background, Controls, MiniMap } from "reactflow";
import "reactflow/dist/style.css";
import { useTopologyStore } from "./store/useTopologyStore";
import { SwitchNode } from "./nodes/SwitchNode";
import { UplinkEdge } from "./edges/UplinkEdge";
import { fetchSnapshot } from "./api/topologyClient";
import { createSseStream } from "./api/sseStream";

const nodeTypes = { switch: SwitchNode };
const edgeTypes = { uplink: UplinkEdge };

// Transport is chosen here and nowhere else — swap createSseStream() for a
// WebSocket implementation later (§12) without changing anything below.
const stream = createSseStream();

export function TopologyMap({
  onSelect,
}: {
  onSelect?: (id: string, kind: "node" | "edge") => void;
}) {
  const { nodes, edges, hydrate, applyPatch, markAllStale } =
    useTopologyStore();

  useEffect(() => {
    let unsub = () => {};
    fetchSnapshot().then((snap) => {
      hydrate(snap);
      unsub = stream.subscribe(applyPatch, markAllStale);
    });
    return () => unsub();
  }, [hydrate, applyPatch, markAllStale]);

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={(_, n) => onSelect?.(n.id, "node")}
        onEdgeClick={(_, e) => onSelect?.(e.id, "edge")}
        fitView
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  );
}
```

---

## 9. Scale Strategy (mandatory)

A fixed layout that breaks past ~30 devices is rejected. Implement:

- **Pan/zoom + minimap** (above) as the baseline.
- **Collapsible subtrees**: clicking a distribution node hides/shows its access children
  (store a `collapsed: Set<string>`, filter nodes/edges before layout).
- **Per-site view**: if `tier`/site metadata grows, allow filtering to one site's tree.
- For very large graphs, gate rendering with React Flow's `onlyRenderVisibleElements`.

---

## 10. Quality Gates (Definition of Done)

- TypeScript strict passes; no `any` in the public contract.
- `treeLayout.ts` and `healthTheme.ts` have unit tests (pure functions — test color/width/rank).
- WS reconnect with backoff; on disconnect, all edges flip to `stale` (dashed) — UI never freezes.
- Keyboard focus + `aria-label` on nodes; respects `prefers-reduced-motion`.
- All thresholds/colors are named constants in one module; zero inline magic values.
- No hardcoded topology anywhere; component renders empty-state cleanly when snapshot is empty.

---

## 11. Build Order (incremental, low-risk)

1. `types.ts` + `healthTheme.ts` (+ tests) — pure core, no UI.
2. `treeLayout.ts` (+ tests).
3. `SwitchNode` / `UplinkEdge` with mock store data — verify visual encoding.
4. `useTopologyStore` + `topologyClient` (initial snapshot, mock backend).
5. `TopologyMap` canvas wiring; confirm backbone renders top-center.
6. `TopologyStream` interface + `sseStream` live patches; confirm diff updates without re-layout
   and that a forced disconnect flips all edges to stale (dashed).
7. Collapsible subtrees + scale gates.
8. Drill-down callback (`onSelect`) handed to the parent dashboard (STEP 3 module).

Implement in this order; each step is independently verifiable.

---

## 12. Future: SSE → WebSocket Migration Path (do NOT build now)

Current backend is server→client only (job submit → client streams status), so SSE is correct and
WebSocket would add connection/heartbeat/reconnect overhead with no benefit. Revisit WebSocket only
when the **client must push upstream continuously** — e.g. changing subscription targets live,
controlling polling cadence, selecting per-device streams, or issuing collect cancel/retry commands.

When that day comes, the change is contained to the transport seam:

- Implement `createWsStream(): TopologyStream` alongside `sseStream.ts`.
- Add upstream methods to a wider interface (e.g. `TopologyStream & { send(cmd: ClientCommand): void }`)
  rather than scattering `socket.send(...)` through components.
- Swap the single `const stream = createSseStream()` line in `TopologyMap.tsx`.
- The store, layout, theme, nodes, and edges remain untouched — they only consume `TopologyPatch`.

This is why §7.1 defines `TopologyStream` as an interface from day one: the seam costs nothing now
and saves a refactor later. Keep SSE until a concrete upstream-control requirement appears; do not
pre-build WebSocket on speculation.
