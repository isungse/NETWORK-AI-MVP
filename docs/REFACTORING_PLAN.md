# STEP 2 Refactoring Plan

Date: 2026-06-22
Scope: design review / Codex work order only. No production code changes are included here.

This plan is based on `docs/CODE_REVIEW.md` after the current refactor. The code already has a collector adapter boundary, service modules, server-side parsing, monitoring SSE, and a dashboard/topology MVP. The remaining work is to turn that foundation into a maintainable NMS-style system for all managed equipment.

## Target 3-Layer Architecture

### 1. Collector Layer

Goal: add vendors/protocols by writing one adapter, without changing API/UI logic.

Target responsibilities:
- Own device communication only.
- Hide protocol differences behind `CollectorAdapter`.
- Support Telnet legacy collection, then SSH/SNMP/gNMI/NETCONF as separate adapters.
- Batch commands per device session where possible.
- Emit structured collection events and raw command artifacts.

Current anchors:
- `src/network_ai_mvp/collector/base.py`
- `src/network_ai_mvp/collector/telnet.py`
- `src/network_ai_mvp/collector/queue.py`
- `src/network_ai_mvp/services/collection_workflow.py`

Required target changes:
- Make `CollectorRegistry.adapter_for(device)` the single execution selector.
- Remove drift between `collector_registry` capability checks and `command_executor` execution.
- Add protocol capability metadata to device/public DTOs.
- Add scheduler-owned queue submission for production polling.

### 2. State / Store Layer

Goal: separate current state from historical time-series state.

Target responsibilities:
- Snapshot store: latest device, port, neighbor, uplink, alarm, and job state.
- History store: timestamped samples for counters, utilization, topology, and alarms.
- Topology store: normalized nodes/edges derived from CDP/LLDP plus optional external reference config.
- Repository interfaces hide whether storage is local JSON, SQLite, Postgres, or TimescaleDB.

Current anchors:
- `src/network_ai_mvp/observations.py`
- `src/network_ai_mvp/audit.py`
- `src/network_ai_mvp/search.py`
- `src/network_ai_mvp/services/topology.py`
- `src/network_ai_mvp/thresholds.py`

Required target changes:
- Add repository interfaces for observations, audit, jobs, topology, and alarms.
- Add atomic writes/file locking while local JSON remains in use.
- Add counter delta/rate calculations from history.
- Persist job state so restart does not lose queue status.
- Keep current snapshot API stable while history endpoints are introduced.

### 3. API / Presentation Layer

Goal: routes are thin, UI renders state, and live changes are pushed to clients.

Target responsibilities:
- FastAPI routes call services and serialize DTOs only.
- UI consumes device/topology/alarm DTOs and does not parse CLI text.
- Live changes use SSE/WebSocket diff updates, not browser polling loops.
- Auth/RBAC gates collection, audit, and future write flows.

Current anchors:
- `src/network_ai_mvp/api.py`
- `src/network_ai_mvp/services/monitoring.py`
- `src/network_ai_mvp/static/index.html`
- `src/network_ai_mvp/static/app.js`
- `src/network_ai_mvp/static/monitoring.js`

Required target changes:
- Add API dependency for identity/role checks.
- Convert the topology UI to a componentized graph implementation.
- Keep alarm feed and dashboard summary as first-class state surfaces.
- Preserve API compatibility where possible; version any breaking DTO changes.

## Current To Target Mapping

| Current location | Target direction | Priority | Risk |
|---|---|---:|---:|
| `api.py:create_app` route closures | Keep as route wiring, but add auth dependencies and delegate any remaining data shaping to services. | P1 | Medium |
| `api.py:DEFAULT_COLLECTOR_REGISTRY` + `CollectionWorkflow.command_executor` | Select and execute through `CollectorRegistry`; avoid separate support and execution paths. | P0 | Medium |
| `collector/queue.py:CollectionQueue` | Keep in-process queue for MVP, then persist job snapshots/results and add scheduler ownership. | P0 | Medium |
| `services/collection_workflow.py` | Split orchestration into command planning, job submission, result persistence, and event publishing services. | P1 | Medium |
| `collector/telnet.py` | Keep as legacy adapter; add SSH/SNMP/gNMI adapters without changing API routes. | P1 | Medium |
| `observations.py` direct JSON writes | Move behind `ObservationRepository`; use atomic local writes first, DB later. | P0 | Medium |
| `audit.py` direct JSONL append | Move behind `AuditRepository`; include principal identity when auth is added. | P1 | Medium |
| `services/topology.py` reference/live merge | Split into topology ingestion, normalization, health calculation, and DTO assembly. | P0 | High |
| `parsers.py:parse_lldp_neighbors` | Expand with fixture-backed CDP/LLDP parsers per vendor/platform. | P0 | Medium |
| `thresholds.py` absolute thresholds | Add history-based rate thresholds and utilization policy. | P0 | Medium |
| `static/app.js` monolith | Replace topology/dashboard sections with componentized UI; React Flow + dagre for topology. | P1 | High |
| `auth.py` / `services/change.py` foundation | Keep isolated; do not expose write execution until RBAC, approvals, simulation, and rollback are complete. | P0 security gate | High |

## Incremental Migration Order

### M1: Normalize Current Architecture Contracts

Scope:
- Make registry-based adapter selection the only collection execution path.
- Keep Telnet behavior unchanged.
- Add tests that assert unsupported devices fail through the registry.

Risk: Medium. It touches the collection path but not device command content.

Acceptance:
- Existing collect/check APIs still work.
- `python -m unittest discover -s tests` passes.
- No credentials or credential refs in public API output.

### M2: Persist Runtime State Safely

Scope:
- Introduce repository interfaces for observations, audit events, jobs, and topology.
- Implement local JSON/JSONL repositories with atomic writes and locking.
- Keep existing file layout compatible.

Risk: Medium. Data corruption prevention must not change response schemas.

Acceptance:
- Corrupt JSON produces degraded/stale state, not an unhandled traceback.
- Parallel queued jobs do not corrupt latest/index files.
- Root runtime log artifacts are ignored or moved outside the repo root.

### M3: Add Production Polling Scheduler

Scope:
- Add scheduler service with per-purpose intervals.
- Submit work through `CollectionQueue`.
- Track last run, next run, stale reason, and failure count per device.
- Push scheduler state to UI through SSE/WebSocket.

Risk: High. Introduces lifecycle and concurrency.

Acceptance:
- One failed/unreachable device does not block other devices.
- UI shows stale/down states explicitly.
- Scheduler can be started/stopped cleanly during app lifespan.

### M4: Build Topology Data Pipeline

Scope:
- Expand CDP/LLDP parsing.
- Normalize nodes/edges into a topology store.
- Support external YAML topology config only as an interim fallback.
- Attach confidence/source fields: live, stale, reference, unmanaged.

Risk: High. Topology correctness affects operator trust.

Acceptance:
- No topology component contains hardcoded device arrays.
- Reference-only edges are visually distinguishable from live edges.
- Backbone/core, distribution, and access tiers can be derived or configured.

### M5: Implement Uplink Health Model

Scope:
- Store counter history.
- Compute utilization, error/discard rates, oper/admin state, stale status, and port-channel member state.
- Attach health to inter-switch edges.
- Raise alarm feed events on threshold crossings.

Risk: Medium to high. Requires historical correctness.

Acceptance:
- Edge color and thickness are derived from metrics, not hardcoded.
- Stale links remain visible as stale, never disappearing silently.
- Tests cover counter reset, missing samples, and threshold crossing.

### M6: Rework Dashboard / Topology UI

Scope:
- Move to componentized topology surface using React Flow + dagre, or an equivalent maintainable graph layer.
- Keep top global health summary, center topology, and alarm feed.
- Add switch/link drill-down.
- Add pan/zoom, collapsible subtrees, and per-site view strategy.

Risk: High. UI regression risk is visible to operators.

Acceptance:
- Every managed device appears as a node or is listed as unplaced/unlinked with a reason.
- Clicking a node or edge opens actionable detail.
- Layout works beyond one screen through pan/zoom and collapse/site filters.

### M7: Add Auth/RBAC Before Any Write Feature

Scope:
- Add app-level identity.
- Gate collect/check/audit/future write routes by role.
- Require separate operator and approver for write proposals.
- Keep write execution disabled until explicitly approved.

Risk: High. Security-sensitive.

Acceptance:
- Anonymous users cannot trigger collection or view audit logs.
- Write proposals include operator/approver identity and immutable audit records.
- No write execution route exists until a separate approval step.

## Priority And Effort

| Work item | Priority | Rough effort | Why |
|---|---:|---:|---|
| Registry-only collection execution | P0 | S-M | Prevents adapter drift before new protocols. |
| Safe local repositories | P0 | M | Required before scheduled parallel polling. |
| Scheduler and persisted job state | P0 | L | Required for real NMS behavior. |
| CDP/LLDP topology pipeline | P0 | L | Required for all-device UI topology. |
| Uplink health rates/history | P0 | L | Required for edge health rendering. |
| Auth/RBAC gate | P0 | M-L | Required before operational use and any change feature. |
| React Flow + dagre topology UI | P1 | L | Required for commercial-NMS-style operator UI. |
| SSH/SNMP/gNMI adapters | P1 | M-L | Production protocol path beyond Telnet. |
| Frontend module/component split | P1 | M | Reduces UI maintenance risk. |
| Log ignore/cleanup | P2 | S | Reduces accidental artifact commits. |

## Guardrails For Codex Execution

- Do not big-bang rewrite. Each migration must keep `/health`, `/devices`, `/topology`, collect/check, and latest port views working.
- Do not print or commit management IP values, credential refs, passwords, SNMP communities, or credential file paths in documentation beyond structural references.
- Do not expose write execution routes during M1-M6.
- Add tests with each backend change. For UI changes, add browser verification and screenshot checks.
- Any new topology or health field must include source and timestamp metadata so the UI can distinguish live, stale, and reference data.

## STEP 2 Status

STEP 2 is complete as a refactoring design review and Codex work order. It is not an implementation patch.
