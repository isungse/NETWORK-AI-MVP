# STEP 3 Dashboard Information Hierarchy Checklist

Date: 2026-06-22
Scope: review checklist only. Codex implements after approval.

Purpose: make the first screen an operator dashboard, not a data dump. The top surface must show what needs action now; supporting detail moves into drill-down views.

## Information Reduction Rules

- [ ] Hide raw command output from the default dashboard. Raw output belongs in a detail/debug drawer.
- [ ] Hide management IP by default unless the logged-in role is allowed to reveal operational addressing.
- [ ] Hide credential references completely from UI and API responses.
- [ ] Show counts and severity first: fault, warning, stale/unreachable, normal.
- [ ] Show only actionable alarms in the main alarm feed.
- [ ] Move inventory metadata, platform strings, notes, and historical samples into device detail.
- [ ] Do not show duplicate health facts in multiple panels unless one is a compact summary and the other is drill-down detail.
- [ ] Every hidden field must still be reachable from a deliberate detail view when it is operationally useful.

## Required Layout

Top global health band:
- [ ] Shows total devices, critical/fault count, warning count, stale/unreachable count, and last collection age.
- [ ] Uses stable status colors: normal green, warning yellow, fault red, stale gray.
- [ ] Clicking a summary count filters the topology and alarm feed.

Center topology map:
- [ ] Shows all managed devices as nodes, or lists unplaced devices with an explicit reason.
- [ ] Shows switch-to-switch links as edges.
- [ ] Encodes node status from device health.
- [ ] Encodes edge status from uplink health once STEP 5 is implemented.
- [ ] Supports pan/zoom and remains usable beyond one screen.

Right or bottom real-time alarm feed:
- [ ] Shows timestamp, severity, device, affected interface/link, short reason, and source.
- [ ] Supports live updates by SSE/WebSocket diff events.
- [ ] Does not require browser refresh to show new alarms.
- [ ] Allows filtering by severity, device, and source.

## Drill-Down Behavior

Switch node click:
- [ ] Opens a device detail panel.
- [ ] Shows hostname/label, role/tier, status, last seen, latest collection purpose, and active findings.
- [ ] Shows ports grouped by uplink, access, down, disabled, error-heavy, low-speed, and unknown.
- [ ] Shows latest neighbors and whether each neighbor is live, stale, reference-only, or unmanaged.
- [ ] Provides raw command/audit links only in an advanced/debug section.

Link/edge click:
- [ ] Opens uplink detail.
- [ ] Shows local device/interface and remote device/interface.
- [ ] Shows oper/admin status, utilization, error/discard rates, port-channel member status, last sample time, and source confidence.
- [ ] Shows related alarms and recent threshold crossings.

Alarm click:
- [ ] Opens the affected device/link/port context.
- [ ] Preserves the operator's current topology zoom/filter state.

## Data Contract Requirements

- [ ] Dashboard consumes backend DTOs, not CLI text parsing in the browser.
- [ ] Every device status includes `status`, `severity`, `last_seen`, `stale`, and `finding_count`.
- [ ] Every topology edge includes source/target, local/remote interface, source type, status, and timestamp/source confidence when available.
- [ ] Alarm DTOs include stable IDs so repeat events update existing alarms instead of duplicating feed rows.
- [ ] Missing data is rendered as "stale" or "unknown", never as blank UI.

## Review Rejection Criteria

- [ ] Reject if the dashboard first screen is dominated by raw tables and command output.
- [ ] Reject if a failed device removes itself from the topology instead of becoming stale/unreachable.
- [ ] Reject if click actions do not lead to per-port or per-link detail.
- [ ] Reject if the UI depends on hardcoded device names, IPs, or topology arrays.
- [ ] Reject if alarm updates require manual refresh.

## STEP 3 Status

STEP 3 checklist is complete. It defines implementation criteria only.
