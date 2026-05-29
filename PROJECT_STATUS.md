# Project Status

Last updated: 2026-05-29

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
- Audit log writer/reader with redaction in `src/network_ai_mvp/audit.py`.
- Inventory and known-risk diagnostics in `src/network_ai_mvp/diagnostics.py`.
- CLI entrypoint with device listing and command-plan commands.
- Test coverage for API, audit redaction, diagnostics, executor, inventory, and policy.

Current UI behavior:

- Inventory table and device detail panel.
- Purpose selector and allowlisted command plan.
- Read-only `Collect` button.
- Collection Result panel is the primary wide output area.
- Raw `stdout` is rendered as terminal-style text instead of escaped JSON.
- `connected` is highlighted green and `disabled` is highlighted red in collection output.
- `notconnect` is intentionally not colorized.
- Audit Log remains a supporting panel.

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
- Natural-language chat/ask panel.
- Live observation parser/storage pipeline.
- SSH/API replacement for Telnet.

## Verification Results

Latest local verification:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Result:

```text
Ran 25 tests
OK
```

JavaScript syntax check:

```powershell
node --check src\network_ai_mvp\static\app.js
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
0e27051 Initial read-only network AI MVP
```

Uncommitted working-tree changes at checkpoint time:

- `src/network_ai_mvp/static/app.js`
- `src/network_ai_mvp/static/styles.css`
- `PROJECT_STATUS.md`
- `NEXT_TASK.md`

The uncommitted UI changes are intentional and stable:

- terminal-style Collection Result rendering
- green `connected`
- red `disabled`

Ignored runtime artifacts:

- `logs/`
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
- `static/`: local operational UI.

Current maintainability risks:

- Telnet transport is temporary and insecure.
- Raw stdout is returned directly to the browser after redaction; this is acceptable for local MVP but should be stored and referenced by run id later.
- Known risks are manually maintained in `inventory/known_risks.json`; this needs a refresh/update workflow.
- Diagnostics are not yet based on parsed live observations.
- UI is vanilla JavaScript and can remain simple for MVP, but larger interactive features should be modularized.

## Server State

The local FastAPI server was intentionally left running for the user:

```text
http://127.0.0.1:8012/
```

Do not assume it will still be running in the next session. If needed, restart it with credential environment variables.

Example:

```powershell
$env:PYTHONPATH='src'
$env:NETWORK_AI_CREDENTIAL_BACKBONE_ADMIN="$env:USERPROFILE\backbone_admin.cred.xml"
$env:NETWORK_AI_CREDENTIAL_ARISTA_KCL="$env:USERPROFILE\arista_kcl.cred.xml"
python -m uvicorn network_ai_mvp.api:create_app --factory --host 127.0.0.1 --port 8012
```
