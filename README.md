# Network AI MVP

Read-only foundation for a company network management AI agent.

## Current Scope

- Seed inventory from documented Cisco and Arista devices.
- Allowlisted read-only command plans only.
- Low-speed and interface error diagnostic rules.
- Local FastAPI app and dense read-only web UI for inventory, command plans, collection metadata, diagnostics, endpoint lookup, and audit history.

No configuration commands are implemented in this MVP foundation.

## Safety Rules

- Treat Markdown network documentation as reference data, not live truth.
- Re-check live state before any operational decision.
- Do not execute arbitrary AI-generated CLI on devices.
- Use allowlisted command plans from `network_ai_mvp.policy`.
- Do not store plaintext passwords or credential files in this repository.
- Public API responses do not expose internal credential references.
- Telnet access is temporary and insecure; prefer SSH/API for the production MVP.

## Reference Data

Known device risks are stored in `inventory/known_risks.json`. Entries include a `source_classification` of `historical`, `reference`, or `live`. Historical and reference findings are labeled as not live truth in diagnostics output.

## Local Verification

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
```

Install optional API/test dependencies when you want to run the FastAPI service or API endpoint tests:

```powershell
pip install -e .[api]
```

## CLI Examples

```powershell
$env:PYTHONPATH='src'
python -m network_ai_mvp list-devices
python -m network_ai_mvp list-purposes --vendor arista
python -m network_ai_mvp plan-commands --device-id arista-10g-core --purpose topology
```

## Optional API

Start the local read-only API from VS Code or a PowerShell terminal:

```powershell
$env:PYTHONPATH='src'
uvicorn network_ai_mvp.api:create_app --factory --reload
```

Example read-only requests:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/devices
curl http://127.0.0.1:8000/devices/arista-10g-core
curl http://127.0.0.1:8000/vendors/arista/purposes
curl http://127.0.0.1:8000/devices/arista-10g-core/command-plan/topology
curl http://127.0.0.1:8000/devices/arista-1f-outpatient/command-plan/port-endpoints
curl http://127.0.0.1:8000/devices/arista-2f-1/command-plan/security-logs
curl http://127.0.0.1:8000/devices/arista-10g-core/diagnostics
curl http://127.0.0.1:8000/audit-log
```

Live collection is also read-only and policy-limited, but it will open a device session through the existing safe executor wrapper:

```powershell
curl -X POST http://127.0.0.1:8000/devices/arista-10g-core/collect/baseline
curl -X POST http://127.0.0.1:8000/devices/arista-1f-outpatient/collect/port-endpoints
curl -X POST http://127.0.0.1:8000/devices/arista-2f-1/collect/security-logs
```

Use Purpose `port-endpoints` when the operator needs to identify endpoint IP/MAC evidence for a problematic switch port. It uses only allowlisted read-only commands:

- `terminal length 0`
- `show interfaces status`
- `show interfaces description`
- `show mac address-table`
- `show ip arp`

The API response includes `port_endpoint_trace`, and the UI renders it as `PORT ENDPOINT TRACE` before raw stdout.

Use Purpose `security-logs` for approved read-only Arista access/log review. It uses only:

- `terminal length 0`
- `show logging`
- `show users`

Some Arista commands such as `show users` may require privileged mode. The Telnet helper supports an optional encrypted enable credential path, but enable must be used only for explicitly approved read-only checks.

Credential refs from `inventory/devices.csv` map to local encrypted credential file paths through environment variables. Do not put plaintext passwords or credential files in this repository.

```powershell
$env:NETWORK_AI_CREDENTIAL_BACKBONE_ADMIN="$env:USERPROFILE\backbone_admin.cred.xml"
$env:NETWORK_AI_CREDENTIAL_ARISTA_KCL="$env:USERPROFILE\arista_kcl.cred.xml"
```

Collection attempts are appended to `logs/collection_audit.jsonl`. Audit records include device metadata, purpose, allowlisted commands, success/failure, return code, and an error summary, but not passwords.

Telnet support is temporary and insecure. Prefer SSH or an API transport before using this outside the local MVP phase.
