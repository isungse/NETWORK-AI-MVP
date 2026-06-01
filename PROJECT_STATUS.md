# Project Status

Last updated: 2026-06-01

## Project Goal

Build a local read-only AI Network Management Agent MVP for company network diagnostics.

Current operational target:

- Cisco backbone switch diagnostics.
- Arista 10G/core/access switch diagnostics.
- VLAN, LLDP/CDP, MAC/ARP, interface status, error counter, LACP, trunk, and STP checks.
- Read-only collection first.
- Approval-based changes later, starting with single-interface shutdown/no shutdown only after explicit approval.

The SaaS/ERP/customer inventory/Chrome extension goals mentioned in the session shutdown prompt do not apply to this repository. The applicable goal is network diagnostics and operational safety.

## Current Implementation Status

The MVP is usable as a local FastAPI web application at `http://127.0.0.1:8012/` when the server is running.

Implemented:

- Python package under `src/network_ai_mvp`.
- Device inventory in `inventory/devices.csv`.
- Known risk reference data in `inventory/known_risks.json`.
- Read-only command allowlist in `src/network_ai_mvp/policy.py`.
- PowerShell Telnet helper in `scripts/backbone_telnet_readonly.ps1`.
- Python executor wrapper in `src/network_ai_mvp/executor.py`.
- Credential mapping via environment variables in `src/network_ai_mvp/credentials.py`.
- FastAPI backend in `src/network_ai_mvp/api.py`.
- Local web UI served at `/`.
- Monitoring UI served at `/monitoring`.
- Audit log writer/reader with redaction in `src/network_ai_mvp/audit.py`.
- Inventory and known-risk diagnostics in `src/network_ai_mvp/diagnostics.py`.
- Backbone neighbor reference loader in `src/network_ai_mvp/neighbors.py`.
- Backend collection parsers in `src/network_ai_mvp/parsers.py`.
- Local redacted raw/parsed observation storage in `src/network_ai_mvp/observations.py`.
- Deterministic device/port/IP/MAC search in `src/network_ai_mvp/search.py`.
- CLI entrypoint with device listing and command-plan commands.
- Test coverage for API, audit redaction, diagnostics, executor, inventory, and policy.

Current UI behavior:

- Inventory table and device detail panel.
- Purpose selector and allowlisted command plan.
- Read-only `Collect` button.
- Collection Result panel is the primary wide output area.
- Monitoring page mirrors the latest Collection Result in a separate full-height terminal view.
- Connected Neighbors appears under Inventory and links known neighbors into the same Device Detail workflow.
- Raw `stdout` is rendered as terminal-style text instead of escaped JSON.
- `connected` is highlighted green and `disabled` is highlighted red in collection output.
- `notconnect` is intentionally not colorized.
- Purpose `endpoints` collects interface descriptions, MAC table, and ARP table separately from `baseline`.
- Endpoint IP/MAC correlation is displayed under `CONNECTED ENDPOINTS` with one endpoint per line.
- Interface collections show a browser-side `INTERFACE FINDINGS` summary for connected low-speed ports, disabled ports, and high error counters before raw stdout.
- Operations Search supports deterministic device, port, IP, MAC, and reference-neighbor lookup from inventory, stored parsed observations, and reference neighbor data.
- Port Detail shows stored parsed status, VLAN, speed/duplex, endpoint IP/MAC, neighbor fields when available, error counters, source timestamp, and a neutral recent-history state.
- `Diagnose This Port` selects the existing allowlisted `interfaces` purpose and loads the command plan without executing collection.
- One-click device `CHECK` is available from the Inventory header after selecting a device.
- `CHECK` runs only backend-fixed read-only allowlisted purposes: `interfaces`, `endpoints`, `topology`, and `switching`.
- `CHECK` displays five operator-facing items in one place:
  - low-speed negotiated ports
  - high CRC/error/runts counters
  - uplink/LACP/trunk anomaly foundation
  - IP-MAC-Port correlation
  - documented topology vs live observed topology foundation
- Multi-port CHECK details render one port per line for readability.
- Audit Log remains a supporting panel.

## Current Product Direction - 2026-06-01

Natural-language Ask/Chat was prototyped and then deferred.

Reason:

- Rule-based intent mapping is not reliable enough for operational network diagnostics.
- Practical requests such as `BACKBONE-SW 연결 된 Gi3/24 포트를 확인하고 어떤 장비가 연결 된 지 알려주세요` require topology and endpoint evidence, not a guessed generic interface plan.
- The MVP should first make device, port, endpoint, topology, and collection state accurate and inspectable through deterministic UI workflows.

Current priority:

- Build a port/device-centered operations console.
- Persist structured read-only collection observations locally.
- Correlate per-port interface status, LLDP/CDP, MAC, ARP, error counters, speed, and VLAN.
- Keep search and port detail deterministic until structured state is mature enough for any future LLM layer.

Future LLM direction:

- LLM may be revisited only as a bounded intent-extraction and result-summary layer.
- LLM must not generate executable CLI.
- Backend must validate device, interface, and purpose.
- Commands must always come from backend allowlists.
- User approval is still required before collection or any future change action.

## Latest Session Checkpoint - 2026-06-01

### What Changed

- Removed active natural-language Ask/Chat work from the product direction and kept `/ask/plan` removed.
- Added backend parsers for collected read-only output:
  - interface status
  - interface descriptions
  - interface error counters
  - MAC address table
  - IP ARP
  - basic LLDP neighbor table
- Added local redacted observation storage:
  - `data/raw/`
  - `data/observations/`
- Added deterministic state/search APIs:
  - `GET /devices/{device_id}/ports/latest`
  - `GET /devices/{device_id}/ports/{interface}/latest`
  - `GET /search?q=...`
  - `POST /devices/{device_id}/check`
- Added Inventory-top `CHECK` button and `Network Check` result panel.
- Added CHECK result formatting with per-port line breaks for low-speed/error findings.
- Added Operations Search and Port Detail UI.
- Added tests for parser, observation storage, search APIs, `/ask/plan` removal, and one-click CHECK.

### Why It Changed

- The initial Ask/Chat panel was unreliable for real operations because rule-based Korean natural-language mapping could select the wrong diagnostic intent.
- The operator workflow was too complex when users had to choose a purpose, plan commands, collect, then read raw output.
- The desired MVP experience is now: select a device in Inventory, click `CHECK`, and immediately see the major failure-prevention checks.
- Long low-speed port summaries were hard to read when many ports were concatenated onto one line.

### How It Was Resolved

- Kept all network operations read-only and allowlist-based.
- Implemented deterministic CHECK on the backend instead of natural-language command planning.
- CHECK internally uses only existing allowlisted purposes and never accepts user-provided CLI.
- CHECK stores redacted raw and parsed observations after successful collection.
- CHECK summarizes parsed observations into five fixed UI items.
- UI places CHECK beside Inventory controls so the operator does not need to understand command purposes before running the standard check.
- Multi-port findings now use newline-separated details and the UI preserves those line breaks.

### Live Verification Notes

During this session, read-only CHECK was executed against live devices from the local UI/API.

Confirmed examples:

- `cisco-backbone` CHECK completed successfully.
  - No low-speed port found in parsed interface status.
  - No high error counter port found in parsed interface counters.
  - 53 ports had IP/MAC correlation.
  - 12 ports had live neighbor observations.
- `arista-b1f-3` / `B1F_ARI_101.249` CHECK completed successfully.
  - Low-speed negotiated ports were detected:
    - `Et4`: connected, VLAN `101`, `a-100M`
    - `Et27`: connected, VLAN `101`, `a-10M`
  - Later user-visible output also showed multiple 100M/10M low-speed ports on VLAN `101`; the UI was updated to render each port on its own line.

These are live read-only observations from collection time, not permanent network truth.

### Failed Or Discarded

- Browser plugin automation failed in the Windows sandbox with `windows sandbox failed: spawn setup refresh`.
- Headless Chrome CDP was used instead for actual UI verification.
- The first CHECK placement in Device Detail was discarded because it was below the first viewport in narrow layouts.
- CHECK was moved to the Inventory header and result panel to match the operator's selection workflow.
- Full uplink/LACP/trunk anomaly parsing and topology-vs-live mismatch comparison remain foundations, not complete automated verdicts.

### Decisions

- Keep natural-language Ask/Chat deferred.
- Keep CHECK deterministic and fixed-purpose.
- Keep raw Collection Result visible for auditability and troubleshooting.
- Keep missing/immature diagnostics as `UNKNOWN`, not guessed.
- Do not add write/config/change commands.
- Do not add scheduled collection yet.

### Open Follow-Ups

- Add parser-backed LACP/trunk/STP anomaly verdicts.
- Add documented topology vs live observed topology comparison.
- Add run-id history and recent-change comparison.
- Make CHECK result rows link directly to Port Detail for each affected port.
- Add filtering so expected low-speed endpoints can be classified separately from abnormal low-speed links.

## Previous Session Checkpoint - 2026-05-30

### What Changed

- Added backbone neighbor reference inventory in `inventory/backbone_neighbors.json`.
- Added Cisco backbone-neighbor devices with management IPs to `inventory/devices.csv`.
- Added neighbor lookup API and UI linkage.
- Added `/monitoring` page for separate live Collection Result monitoring.
- Added `endpoints` Purpose for endpoint IP/MAC correlation.
- Removed endpoint correlation commands from `baseline`.
- Improved Telnet login failure handling and PowerShell CLIXML error summarization.
- Refined header layout and button alignment.

### Why It Changed

- Operators needed topology-neighbor devices visible and selectable from the main UI.
- Collection Result needed a separate monitoring view for long outputs.
- Endpoint IP/MAC data is important enough to be its own collect category.
- Baseline output became hard to read when endpoint data was mixed into it.
- Some Cisco access switches are reachable on Telnet but reject the tested credentials; failures needed to return quickly and clearly.

### How It Was Resolved

- Kept topology reference data separate from collect inventory.
- Used inventory matching by management IP/hostname so known neighbors can open Device Detail and collect workflows.
- Used browser `localStorage` to mirror the latest Collection Result into `/monitoring`.
- Rendered endpoint correlation as grouped multiline output under `CONNECTED ENDPOINTS`.
- Added Telnet prompt handling for username/password and password-only flows.

### Failed Or Discarded

- `Open` / `Plan only` neighbor actions were replaced by `Detail` and row-click behavior.
- Double-click neighbor selection was replaced by single-click behavior.
- Using existing `backbone_admin` and `arista_kcl.cred.xml` credentials against `172.16.102.250` failed with `Login failed.`
- Browser automation remained unreliable in the Windows sandbox; local HTTP, JS syntax checks, and unit tests were used instead.

### Decisions

- Maintain read-only-only MVP scope.
- Keep `Gi3/38` as neighbor-only because no management IP is configured.
- Use `endpoints` as a separate Purpose instead of expanding `baseline`.
- Do not persist plaintext credentials or new credential files in the repository.
- Keep Monitoring as local browser state until collection run storage exists.
- Defer natural-language Ask/Chat until structured network state and port-centered workflows exist.

### Open Follow-Ups

- Confirm Cisco access-switch Telnet credentials with the network management vendor.
- Add persisted collection run storage and run IDs.
- Move endpoint correlation and diagnostics out of browser-only parsing into backend parsed observations.
- Replace Telnet with SSH/API where possible.
- Build a port/device-centered operations console before revisiting natural-language Ask/Chat.

## Network Knowledge Captured

Confirmed through docs and read-only checks:

- Cisco backbone:
  - `cisco-backbone`
  - `BACKBONE-SW`
  - `172.16.1.1`
  - `WS-C4503-E`
  - Telnet currently works; SSH previously failed.
- Arista 10G core:
  - `arista-10g-core`
  - `9F_BB_ARI_17.2`
  - `172.17.17.2`
  - `DCS-7050SX3-48YC8-F`
  - Cisco `Te1/3` maps to Arista `Et47`.
  - Cisco `Te1/4` maps to Arista `Et48`.
  - `Po10` LACP is the Cisco/Arista 10G bundle.
- Arista access switches are seeded in `inventory/devices.csv`.
- Backbone neighbor reference is stored in `inventory/backbone_neighbors.json`.
- `Gi3/38` is the 9F computer room Cisco switch, but it has no management IP configured and is not collect-capable.
- `172.16.102.250` Telnet TCP/23 is reachable, but tested stored credentials were rejected.

Known high-priority risks:

- `172.16.33.251 / arista-3f / Ethernet52`: latest live check showed errdisabled uplink indication.
- `172.16.105.249 / arista-2f-outpatient / Ethernet6`: latest live check showed high FCS/Rx/Runts counters.
- `172.16.105.249 / Ethernet1`: historical high-error 10M port, shut down with explicit approval to identify endpoint/terminal.
- `172.16.105.249 / Ethernet15`: historical 10M port, shut down with explicit approval to identify endpoint/terminal.
- Telnet remains temporary and insecure.

## Safety Model

Current mode is read-only.

Enforced rules:

- No arbitrary CLI entry in the UI.
- Commands are selected only through allowlisted purposes.
- Public API responses do not expose `credential_ref`.
- Audit and error paths redact password/secret/token/credential-like values and `.cred.xml` paths.
- Runtime logs and credential files are ignored by git.

Not implemented yet:

- Approval-based change workflow.
- `shutdown/no shutdown` executor.
- `write memory` or persistent config changes.
- Natural-language chat/ask panel. A prototype was removed from active code and deferred.
- Complete live observation parser/storage pipeline. Initial local redacted raw/parsed latest-state storage exists, but historical comparison and broader neighbor/detail parsing remain incomplete.
- SSH/API replacement for Telnet.

## Verification Results

Latest local verification:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Result:

```text
Ran 38 tests
OK
```

JavaScript syntax check:

```powershell
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
```

Result: passed.

API health check:

```text
GET http://127.0.0.1:8012/health
```

Result:

```json
{"status":"ok","mode":"read-only"}
```

UI/API checks also confirmed:

- `GET /` returns the main UI with Inventory CHECK and Operations Search.
- `GET /monitoring` returns the Monitoring page.
- `POST /ask/plan` returns `404 Not Found`.
- `POST /devices/{device_id}/check` works for read-only allowlisted CHECK when credentials are available.

CLI command-plan check:

```powershell
$env:PYTHONPATH='src'; python -m network_ai_mvp plan-commands --device-id cisco-backbone --purpose baseline
```

Result: returned only allowlisted read-only commands.

Diagnostics API check:

```text
GET /devices/arista-2f-outpatient/diagnostics
```

Result: includes Ethernet6, Ethernet1, Ethernet15, Telnet warning, and `Not live truth` labels for historical/reference data.

## Current Git State

Last pushed commit:

```text
2d7aea2 Add topology neighbors and monitoring view
```

Working tree at latest pushed checkpoint:

- Not clean as of the 2026-06-01 session shutdown.
- Multiple implementation and documentation changes are intentionally uncommitted.
- Pre-existing dirty files from earlier work may still be present; do not revert without inspection.

Ignored runtime artifacts:

- `logs/`
- `data/`
- `src/network_ai_mvp.egg-info/`
- `__pycache__/`

## Architecture Notes

Current separation of concerns:

- `inventory.py`: inventory loading and validation.
- `policy.py`: read-only command allowlist.
- `executor.py`: validated command execution through the PowerShell helper.
- `credentials.py`: credential reference to local encrypted credential path.
- `audit.py`: audit event creation, append-only JSONL, redaction.
- `diagnostics.py`: inventory and known-risk diagnostics.
- `api.py`: FastAPI app and endpoint composition.
- `neighbors.py`: backbone neighbor reference loading and lookup.
- `static/`: local operational UI.

Current maintainability risks:

- Telnet transport is temporary and insecure.
- Raw stdout is returned directly to the browser after redaction; this is acceptable for local MVP but should be stored and referenced by run id later.
- Monitoring currently mirrors latest output through browser `localStorage`; this should become run-id based once observation storage exists.
- Known risks are manually maintained in `inventory/known_risks.json`; this needs a refresh/update workflow.
- Diagnostics are not yet based on parsed live observations.
- Endpoint correlation is currently rendered in the browser from raw output and should move to backend parsed observations.
- UI is vanilla JavaScript and can remain simple for MVP, but larger interactive features should be modularized.

## Server State

The local FastAPI server was intentionally left running for the user:

```text
http://127.0.0.1:8012/
```

At shutdown, port `8012` was listening with the latest source loaded.

Do not assume it will still be running in the next session. If needed, restart it with credential environment variables.

Example:

```powershell
$env:PYTHONPATH='src'
$env:NETWORK_AI_CREDENTIAL_BACKBONE_ADMIN="$env:USERPROFILE\backbone_admin.cred.xml"
$env:NETWORK_AI_CREDENTIAL_ARISTA_KCL="$env:USERPROFILE\arista_kcl.cred.xml"
python -m uvicorn network_ai_mvp.api:create_app --factory --host 127.0.0.1 --port 8012
```
