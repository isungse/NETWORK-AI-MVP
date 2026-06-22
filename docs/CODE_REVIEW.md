# STEP 1 Code Review

Date: 2026-06-22
Scope: current working tree review only. No production code changes were made in this step.

This document replaces the older pre-refactor review notes. The current code has already been split into collector and service modules, but the larger objective, converting all managed equipment into a complete NMS-style UI workflow, is not complete yet.

Sensitive inventory values are intentionally not printed here. Findings refer to field names and files only.

## Current Structure

### Runtime and Dependencies

- Backend: Python package under `src/network_ai_mvp`.
- API: FastAPI factory in `src/network_ai_mvp/api.py`; optional API dependencies are declared in `pyproject.toml`.
- Frontend: static HTML/CSS/vanilla JavaScript under `src/network_ai_mvp/static`.
- Database: none configured. Runtime data is written to local files under ignored directories.
- Device inventory: CSV/JSON files under `inventory/`.
- Tests: `tests/` contains backend unit/API tests. Frontend behavior is not covered by a committed browser/unit test suite.

### Layer Separation

- Collector layer exists:
  - `src/network_ai_mvp/collector/base.py` defines `CollectorAdapter`, `CommandResult`, and `CollectorRegistry`.
  - `src/network_ai_mvp/collector/telnet.py` implements the current Telnet/PowerShell collector.
  - `src/network_ai_mvp/collector/queue.py` implements asynchronous in-process job execution.
- Service layer exists:
  - `src/network_ai_mvp/services/collection_workflow.py` owns collection/check orchestration.
  - `src/network_ai_mvp/services/topology.py` builds topology payloads.
  - `src/network_ai_mvp/services/check.py` builds interface findings.
  - `src/network_ai_mvp/services/change.py` contains a write-change proposal foundation, not an active API execution route.
- API/presentation layer is lighter than before:
  - `src/network_ai_mvp/api.py` is now mainly route wiring and response conversion.
  - Static UI still remains a large browser script in `src/network_ai_mvp/static/app.js`.

### Polling and Collection Flow

- Synchronous collection:
  - `POST /devices/{device_id}/collect/{purpose}` calls `CollectionWorkflow.collect`.
  - `POST /devices/{device_id}/check` calls `CollectionWorkflow.check`.
  - The workflow invokes `command_executor.run(...)` directly.
- Asynchronous collection:
  - `POST /devices/{device_id}/collect/{purpose}/jobs` and `/check/jobs` submit work to `CollectionQueue`.
  - `CollectionQueue` uses `ThreadPoolExecutor`.
  - Job state is held in memory.
- Scheduled polling:
  - No scheduler, interval policy, or persistent polling lifecycle is currently implemented.

## Findings

### F-01: Scheduled NMS Polling Is Still Missing

- Location: `src/network_ai_mvp/api.py:228`, `src/network_ai_mvp/api.py:236`, `src/network_ai_mvp/collector/queue.py:59`, `src/network_ai_mvp/services/collection_workflow.py:45`.
- Problem: The system can collect on demand or through an in-memory queue, but it does not yet run continuous NMS polling across all devices.
- Evidence: API routes expose manual collect/check endpoints. `CollectionQueue.submit` only runs jobs that were explicitly submitted, and the code search found no scheduler, interval, cron, or long-running polling service in `src/`.
- Recommended fix direction: Add a scheduler service with per-purpose intervals, per-device backoff, queue backpressure, stale detection, and persisted run history. UI state should show last poll, next poll, stale reason, and collection health per device.

### F-02: Collector Abstraction Exists, But Only Telnet/PowerShell Is Wired

- Location: `src/network_ai_mvp/api.py:29`, `src/network_ai_mvp/collector/base.py:26`, `src/network_ai_mvp/collector/telnet.py:15`, `src/network_ai_mvp/collector/telnet.py:68`.
- Problem: The adapter boundary is a good refactor, but the active registry still contains only the PowerShell Telnet executor.
- Evidence: `DEFAULT_COLLECTOR_REGISTRY` is initialized with one Telnet-backed executor. The Telnet collector shells out via `subprocess.run`.
- Recommended fix direction: Keep the adapter interface, then add SSH/SNMP/gNMI/NETCONF-capable adapters behind capability flags. Prefer SSH/SNMP for production polling and leave Telnet as legacy or lab-only.

### F-03: Topology Is Still Reference-Heavy And Not A Full Live Device Graph

- Location: `src/network_ai_mvp/services/topology.py:18`, `src/network_ai_mvp/services/topology.py:44`, `src/network_ai_mvp/services/topology.py:112`, `src/network_ai_mvp/parsers.py:191`.
- Problem: The topology endpoint can render all inventory nodes, but edge discovery still depends heavily on reference neighbor data and shallow live LLDP/CDP extraction.
- Evidence: `build_topology` merges `_reference_edges(load_backbone_neighbors(...))` with `_live_edges(...)`. Live edges depend on parsed port fields such as `neighbor_name` and `neighbor_ip`, while `parse_lldp_neighbors` is a simple table parser.
- Recommended fix direction: Implement robust CDP/LLDP parsers per vendor/platform, normalize neighbor identifiers, persist topology observations separately from port observations, and make the UI distinguish live, stale, reference-only, and unmanaged links.

### F-04: Port Health Uses Absolute Thresholds, Not Time-Based Rates

- Location: `src/network_ai_mvp/thresholds.py:7`, `src/network_ai_mvp/thresholds.py:30`, `src/network_ai_mvp/services/check.py:82`, `src/network_ai_mvp/observations.py:148`.
- Problem: Error detection is based on absolute counter values and low negotiated speed. It does not calculate deltas, utilization, error rates, flap frequency, or interface trend state.
- Evidence: `HIGH_ERROR_COUNTER_THRESHOLD` and `LOW_SPEED_CONNECTED_THRESHOLD_MBPS` are static checks. Observation summaries count states, but do not compare two samples.
- Recommended fix direction: Store timestamped counter samples, compute deltas/rates, detect counter resets, and classify uplink/access severity using role and interface metadata.

### F-05: API Routes Are Not Protected By App-Level Authentication/RBAC

- Location: `src/network_ai_mvp/auth.py:14`, `src/network_ai_mvp/auth.py:19`, `src/network_ai_mvp/api.py:84`, `src/network_ai_mvp/api.py:228`.
- Problem: An auth/RBAC module exists, but API routes do not use FastAPI dependencies or request authentication.
- Evidence: `Principal`, `require_role`, and `require_distinct_approver` are present. `api.py` route declarations do not require a principal for read, collect, check, or audit-log routes.
- Recommended fix direction: Add local/offline-compatible authentication, role dependencies, audit identity capture, and separate operator/approver roles before exposing any future write route.

### F-06: Sensitive Inventory Fields Are Structurally Present And Some API Responses Expose Management IPs

- Location: `inventory/devices.csv:1`, `src/network_ai_mvp/inventory.py:11`, `src/network_ai_mvp/credentials.py:17`, `src/network_ai_mvp/services/collection.py:14`, `src/network_ai_mvp/api.py:111`.
- Problem: The inventory necessarily contains management addressing and logical credential references. Credential refs are validated as logical names and audit output is redacted, but public device/diagnostic responses still include management IP fields.
- Evidence: Required inventory columns include `management_ip` and `credential_ref`. `resolve_credential_path` maps credential refs through environment variables. `public_device` returns `management_ip`, and diagnostics response includes the same field.
- Recommended fix direction: Keep credentials out of files and responses, continue redaction, and add response profiles so normal UI users see labels/status while privileged operators can reveal management addresses when needed.

### F-07: Local JSON/JSONL Persistence Is Not Atomic Or Concurrency-Hardened

- Location: `src/network_ai_mvp/observations.py:170`, `src/network_ai_mvp/observations.py:186`, `src/network_ai_mvp/audit.py:78`, `src/network_ai_mvp/services/change.py:57`.
- Problem: Runtime state is written to local JSON/JSONL files without atomic temp-file replacement, file locks, or a database transaction boundary.
- Evidence: `_write_json` calls `path.write_text(...)`; audit and change proposal writers append directly to JSONL files. The collection queue can run multiple jobs in parallel.
- Recommended fix direction: Use atomic write-and-replace for JSON files, file locking for local mode, and plan migration to SQLite/Postgres/TimescaleDB for polling history and audit records.

### F-08: Queued Job State Is In-Memory Only

- Location: `src/network_ai_mvp/collector/queue.py:61`, `src/network_ai_mvp/collector/queue.py:66`, `src/network_ai_mvp/api.py:244`.
- Problem: Async jobs disappear on process restart and cannot be queried across sessions.
- Evidence: `CollectionQueue` stores `_jobs` and `_futures` dictionaries in memory. `/collection-jobs/{job_id}` reads from that in-memory queue.
- Recommended fix direction: Persist job metadata and results, expire old jobs with retention policy, and expose collection history separately from currently running jobs.

### F-09: Some Reference/Runtime Data Errors Can Still Escape As 500s

- Location: `src/network_ai_mvp/api.py:129`, `src/network_ai_mvp/api.py:136`, `src/network_ai_mvp/neighbors.py:22`, `src/network_ai_mvp/observations.py:111`, `src/network_ai_mvp/observations.py:124`.
- Problem: Several routes handle inventory errors, but not all malformed runtime/reference JSON cases are translated into clear API errors.
- Evidence: `/topology` catches `ValueError`, but `/devices/{device_id}/neighbors` calls `get_neighbors_for_device(...)` without catching malformed reference JSON errors. Observation readers catch some decode errors by returning empty state, which can hide data corruption.
- Recommended fix direction: Define repository-level exceptions for reference data and runtime store corruption, map them consistently to `503` or structured degraded-state responses, and surface corruption warnings in the UI.

### F-10: Frontend Is Still A Large Static Script With Manual Topology Layout

- Location: `src/network_ai_mvp/static/app.js:482`, `src/network_ai_mvp/static/app.js:553`, `src/network_ai_mvp/static/app.js:627`, `src/network_ai_mvp/static/app.js:686`, `src/network_ai_mvp/static/app.js:1331`.
- Problem: The UI now contains dashboard and topology behavior, but it is still a monolithic vanilla JS file with manual SVG link calculation.
- Evidence: `app.js` runs to line 1331. Dashboard loading, topology node rendering, link rendering, edge click behavior, search, collection, and detail panels live in one file.
- Recommended fix direction: For the directive target, move topology to a componentized UI using React Flow plus dagre/elk-style layout, or at minimum split vanilla modules by dashboard, topology, devices, audit, and collection jobs.

### F-11: The UI Shows Equipment, But It Is Not Yet A Complete Device-Centric NMS Workspace

- Location: `src/network_ai_mvp/static/index.html:206`, `src/network_ai_mvp/static/app.js:482`, `src/network_ai_mvp/static/app.js:553`, `src/network_ai_mvp/services/topology.py:223`.
- Problem: The current screen can display inventory nodes, summaries, alarms, topology, and port detail, but it is not yet the final "all equipment converted into UI form" workflow.
- Evidence: Topology summary is produced in backend, and `app.js` renders the dashboard/topology. Missing pieces include scheduler status, topology confidence, device drill-down lifecycle, historical trends, role-aware actions, and full network hierarchy layout.
- Recommended fix direction: Treat the current UI as an MVP dashboard. The next UI phase should make every managed device a first-class node with status, ports, uplinks, neighbors, last collection, active alarms, history, and safe action state.

### F-12: Write-Change Foundation Must Stay Isolated Until Auth, Approval, And Simulation Are Complete

- Location: `src/network_ai_mvp/write_policy.py:8`, `src/network_ai_mvp/write_policy.py:33`, `src/network_ai_mvp/services/change.py:32`, `src/network_ai_mvp/api.py:228`.
- Problem: A write policy/proposal foundation exists, but the API currently exposes only collect/check flows. This is the correct safer state, but it becomes high risk if wired prematurely.
- Evidence: `write_policy.py` can build interface admin commands. `services/change.py` requires distinct operator/approver principals. `api.py` does not expose a write execution route.
- Recommended fix direction: Keep write actions disabled until dry-run simulation, RBAC, approval records, maintenance windows, rollback plans, and explicit allowlists are implemented and tested.

### F-13: Parser Logic Is Useful But Still Brittle For Multi-Vendor Production Inputs

- Location: `src/network_ai_mvp/parsers.py:89`, `src/network_ai_mvp/parsers.py:134`, `src/network_ai_mvp/parsers.py:155`, `src/network_ai_mvp/parsers.py:191`, `src/network_ai_mvp/parsers.py:269`.
- Problem: Parsers rely mainly on line splitting and interface-name heuristics. That is acceptable for the MVP sample commands, but fragile against CLI format variation.
- Evidence: Interface status, error counters, MAC table, ARP, and LLDP parsing all use split-based extraction. `_looks_like_interface` is the main interface classifier.
- Recommended fix direction: Add fixture-driven parser tests per vendor/platform/command, support CDP detail and LLDP detail formats, and record parse confidence/errors in observations.

### F-14: Runtime Log Artifacts Can Still Be Accidentally Added

- Location: `.gitignore:7`, `.gitignore:11`, repository root runtime files from current status.
- Problem: `logs/` and `data/` are ignored, but root-level server log files are currently untracked and not covered by a generic log ignore rule.
- Evidence: `.gitignore` ignores `logs/` and `logs/*.jsonl`, but not root `*.log`. `git status --short` shows root server log files as untracked.
- Recommended fix direction: Add a non-production cleanup step or ignore pattern for local server runtime logs. Do this outside the review-only workflow or in the implementation phase after approval.

## Duplicate / Unused / Removal Candidates

These are not immediate delete instructions; they are review candidates that need call-site checks before removal.

1. `command_executor` and `collector_registry` are both passed into `CollectionWorkflow`.
   - Location: `src/network_ai_mvp/services/collection_workflow.py:32`, `src/network_ai_mvp/services/collection_workflow.py:39`.
   - Problem: The registry is used for capability reporting/support checks, while execution still goes through a separately injected executor. This can drift if more adapters are added.
   - Evidence: Queue submission uses `adapter=self.command_executor`; support checks use `collector_registry`.
   - Recommended fix direction: Have the workflow select the adapter from the registry for both support checks and execution, then remove the separate executor parameter if no longer needed.

2. Manual topology link layout duplicates concerns that a graph layout library should own.
   - Location: `src/network_ai_mvp/static/app.js:553`, `src/network_ai_mvp/static/app.js:627`.
   - Problem: UI code manually computes node/link placement and edge interaction.
   - Evidence: `renderTopologyMap` and `renderTopologyLinks` perform DOM query and SVG path work directly.
   - Recommended fix direction: Replace with React Flow/dagre in the STEP 4 implementation path, or isolate it into a dedicated topology module if staying vanilla.

3. Local file stores duplicate concerns that should move behind repositories.
   - Location: `src/network_ai_mvp/audit.py:78`, `src/network_ai_mvp/observations.py:186`, `src/network_ai_mvp/services/change.py:57`.
   - Problem: Audit, observations, and change proposals each write local files directly.
   - Evidence: Each module opens/writes files itself rather than using a shared persistence interface.
   - Recommended fix direction: Introduce repository interfaces for audit, observations, jobs, and proposals before adding scheduled polling.

## High-Risk Refactor Areas

- Collection execution path:
  - `api.py` -> `CollectionWorkflow` -> `command_executor`/`CollectionQueue` -> collector adapter -> PowerShell script.
  - Risk: adding more protocols without unifying adapter selection can create mismatched capability and execution behavior.
- Topology path:
  - inventory + latest observations + reference neighbors -> `build_topology` -> static UI.
  - Risk: UI may look complete even when edges are reference-only or stale.
- Persistence path:
  - collection jobs, audit events, observations, and change proposals are currently separate local files.
  - Risk: scheduled parallel polling will increase race/corruption risk.
- Security path:
  - inventory has sensitive operational fields, credentials are resolved locally, API routes are not authenticated.
  - Risk: future write features must not be exposed until identity and authorization are enforced.

## STEP 1 Status

STEP 1 is complete as a review document. It does not mean the NMS/UI conversion is complete.

Recommended next approval gate: STEP 2 refactoring strategy and target architecture plan.
