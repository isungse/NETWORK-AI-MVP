# STEP 4 Topology UI Hierarchical Tree Checklist

Date: 2026-06-22
Scope: review checklist and design contract only. Codex implements after approval.

Purpose: the topology must look and behave like a commercial NMS hierarchy: backbone/core at the top, distribution in the middle, access switches below, with switch-to-switch edges representing uplinks.

## Chosen Auto-Layout Strategy

Recommended implementation: React Flow + dagre.

Justification for a solo maintainer:
- React Flow provides mature graph interaction primitives: nodes, edges, pan, zoom, controls, click handlers, and custom renderers.
- dagre provides deterministic top-to-bottom hierarchical layout without hand-written coordinate math.
- The current `static/app.js` manually computes SVG links and DOM positions; that approach will become brittle as the device count grows.
- React Flow + dagre lets Codex keep layout code small and testable while focusing project logic on network state.

Acceptable fallback:
- D3 `tree()` or `cluster()` may be used only if the implementation remains componentized and avoids hardcoded coordinates.

## Required Geometry

- [ ] Layout direction is `TB` top-to-bottom.
- [ ] Backbone/core device is resolved as the tree root and placed top-center.
- [ ] L3 distribution switches form the middle tier.
- [ ] L2 access switches form the bottom tier.
- [ ] Switch-to-switch links are edges connecting parent and child nodes.
- [ ] Cross-links or unmanaged links are visually distinct from the main parent-child tree.
- [ ] Devices that cannot be placed are shown in an "unplaced/stale/reference-only" group with reasons.

## Data Source Rules

- [ ] Nodes and edges come from API/state, never literal arrays inside the component.
- [ ] Primary source is CDP/LLDP-derived topology.
- [ ] If live neighbor discovery is incomplete, use an external YAML/JSON topology reference file as an interim source.
- [ ] Reference topology must be labeled as reference-only until confirmed by live data.
- [ ] API payload must include enough metadata for UI trust: `source_type`, `last_seen`, `stale`, `confidence`, and `discovery`.
- [ ] No management IP values, credential refs, or secret names are embedded in frontend code.

## Node Contract

Each node should have:
- [ ] Stable `id`.
- [ ] Display label/hostname.
- [ ] Tier: backbone/core, distribution, access, unknown.
- [ ] Status: normal, warning, fault, stale/unreachable.
- [ ] Last seen timestamp.
- [ ] Finding/alarm count.
- [ ] Click handler that opens device drill-down from STEP 3.

Node color:
- [ ] Green = normal.
- [ ] Yellow = warning.
- [ ] Red = fault.
- [ ] Gray = unreachable/stale.
- [ ] Colors come from a centralized theme/status module, not inline scattered literals.
- [ ] Dark-mode and color-blind readability are considered through labels/icons, not color alone.

## Edge Contract

Each edge should have:
- [ ] Stable `id`.
- [ ] Source device and target device.
- [ ] Local interface and remote interface when known.
- [ ] Source type: live, stale-live, reference, unmanaged, inferred.
- [ ] Health status from STEP 5 when available.
- [ ] Click handler that opens link/uplink drill-down from STEP 3.

Edge rendering:
- [ ] Color is derived from status/health.
- [ ] Thickness or dash style is derived from utilization/capacity/staleness.
- [ ] Reference-only edges are visually distinct.
- [ ] Stale edges stay visible and are marked stale; they do not disappear silently.

## Scale Strategy

- [ ] Pan/zoom controls are present.
- [ ] Collapsible subtrees are available for large access layers.
- [ ] Per-site or per-floor filtering is supported once inventory metadata exists.
- [ ] Search/focus action can center a selected device.
- [ ] N > 30 devices does not rely on a fixed pixel layout.
- [ ] N > 100 devices has a strategy: collapse by tier/site, virtualize side panels, and render only visible detail lists.
- [ ] Manual node repositioning, if offered, persists per user/session and does not overwrite automatic layout source data.

## Implementation Contract For Codex

- [ ] Create a dedicated topology component/module rather than expanding `static/app.js`.
- [ ] Keep layout as a pure function: input nodes/edges -> positioned nodes/edges.
- [ ] Keep health-to-style mapping as pure functions with unit tests.
- [ ] Fetch topology from backend DTOs.
- [ ] Subscribe to SSE/WebSocket diff events and patch node/edge state.
- [ ] Keep the existing MVP page working during migration, or ship the new topology behind a clear feature flag/path.

## Review Rejection Criteria

- [ ] Reject if backbone/distribution/access positions are manually hardcoded.
- [ ] Reject if topology arrays live inside React/JS component source.
- [ ] Reject if lines are not clickable.
- [ ] Reject if edge status is hardcoded rather than derived from metrics/source state.
- [ ] Reject if stale/unreachable devices are hidden.
- [ ] Reject if the layout breaks when device count grows beyond the current inventory.

## STEP 4 Status

STEP 4 checklist is complete. It defines the topology implementation target; it is not production code.
