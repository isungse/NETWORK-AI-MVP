# STEP 0 — Current-State Discovery

> Source directive: `docs/NETWORK_NMS_CODE_REVIEW_DIRECTIVE.md`
> Scope: Review-only discovery. No production code changes.
> Rule: Sensitive values such as device credentials, credential refs, and management IP values are not printed here.

## Discovery Table

| Item | Current state | Evidence | Confidence / action |
|---|---|---|---|
| Backend language/framework | Python package with FastAPI optional API served by Uvicorn. | `pyproject.toml` optional dependency group `api`; `src/network_ai_mvp/api.py` creates `FastAPI(...)`; README API startup command uses `uvicorn network_ai_mvp.api:create_app --factory --reload`. | Confirmed from code. |
| Frontend | Static HTML/CSS/vanilla JavaScript served by FastAPI `StaticFiles`; browser uses `fetch(...)` and `EventSource` for monitoring stream. | `src/network_ai_mvp/static/index.html`, `app.js`, `monitoring.js`; `src/network_ai_mvp/api.py` mounts `/static`; `monitoring.js` creates `EventSource("/events/monitoring")`. | Confirmed from code. |
| DB / persistent store | No database dependency configured. Local files are used for inventory, known risks, audit JSONL, raw output, and parsed observations. | `pyproject.toml` has no DB dependency; `inventory/*.csv/json`; `logs/collection_audit.jsonl` described in README; `src/network_ai_mvp/observations.py` writes JSON under local `data/`; `src/network_ai_mvp/audit.py` reads/writes JSONL. | Confirmed from code. |
| Deployment model | Local on-prem style FastAPI app; documented local URL and local credential environment mapping. | README “Optional API”; `PROJECT_STATUS.md` says local FastAPI web application; API binds to localhost in documented commands. | Confirmed local deployment. Production deployment model is NEEDS CONFIRMATION. |
| Data collection method | CLI scraping through Telnet using a PowerShell helper and allowlisted `show ...` commands. No implemented SNMP/gNMI/NETCONF collector found. Syslog appears only as future/confirmation topic, not implemented ingestion. | `src/network_ai_mvp/collector/telnet.py`; `scripts/backbone_telnet_readonly.ps1`; `src/network_ai_mvp/policy.py` allowlisted commands; `rg` found no implemented SNMP/gNMI/NETCONF modules. | Confirmed current method: Telnet CLI scraping. Future protocol target NEEDS CONFIRMATION. |
| Target vendors / OS families | Cisco and Arista are the only inventory vendors. Platforms include Cisco Catalyst-class switches and Arista EOS-class switches. | `inventory/devices.csv` vendors: `cisco`, `arista`; platforms include Cisco WS-C series and Arista DCS series; README says Cisco and Arista devices. | Confirmed from inventory. Nexus is NEEDS CONFIRMATION; Catalyst is present by platform family. |
| Polling interval | No scheduled polling interval found. Collection is manual/on-demand via API/UI, with queued job endpoints available. | `PROJECT_STATUS.md` says “Do not add scheduled collection yet”; `src/network_ai_mvp/api.py` exposes collect/check and job endpoints; `src/network_ai_mvp/collector/queue.py` uses `ThreadPoolExecutor` but no scheduler. | NEEDS CONFIRMATION for desired production polling interval. |
| Device count | 23 managed inventory devices. | `Import-Csv inventory/devices.csv` count = 23. | Confirmed from inventory. |
| Total port count | Latest local parsed observations currently sum to 964 ports across 23 devices. This is observation-derived runtime state, not an authoritative design capacity. | `data/observations/**/latest.json` summary aggregation: `latest_observation_devices=23`, `latest_observation_total_ports=964`. | Current observed value confirmed. Target/design total port count NEEDS CONFIRMATION. |
| On-prem / air-gapped status | Code and docs indicate local/on-prem operation. Air-gapped status is not explicitly stated. | Local FastAPI app and local credential-file mapping in README/PROJECT_STATUS; no explicit “air-gapped” statement found. | On-prem/local confirmed. Air-gapped NEEDS CONFIRMATION. |
| Authentication method | Device access uses logical credential references resolved to local encrypted credential file paths via environment variables. Application-level user authentication is not evident in API routes. | `src/network_ai_mvp/credentials.py`; `inventory.py` validates credential ref is logical, not a path; README documents env-var mapping; API route definitions have no auth dependency. | Device credential mapping confirmed. App user auth model NEEDS CONFIRMATION / currently absent from code evidence. |
| Read-only vs config changes | Current UI/API collection path is read-only and allowlist-based. There is a foundation for approval-based single-interface admin-state changes, but no active API execution route for changes is evident. | README says no configuration commands are implemented in MVP foundation; `src/network_ai_mvp/policy.py` blocks non-read-only commands; `src/network_ai_mvp/write_policy.py` and `services/change.py` exist; tests assert change route remains absent. | Current system is read-only monitoring/diagnostics. Future approved config changes are planned but not active. |

## Security Discovery Note

| Location | Problem | Evidence | Recommended fix direction |
|---|---|---|---|
| `inventory/devices.csv`, `src/network_ai_mvp/credentials.py`, README credential setup | Inventory contains management IP fields and logical credential references; docs describe local credential file mapping. Values are not printed here. This is expected for the MVP but is sensitive operational metadata. | Inventory schema includes `management_ip` and `credential_ref`; credential resolver maps refs to environment variables; README says credential files must not be committed. | Keep credential values and files outside the repository. Keep public API serializers hiding credential refs. For production, move to a real secret store and replace Telnet with SSH/API/SNMPv3/gNMI TLS where feasible. |

## Questions For Approval / Confirmation

1. What is the intended production polling interval for interface status, counters, topology, and security events?
2. Is the deployment target strictly on-prem, and is the management environment air-gapped?
3. Should the long-term collection protocol target be SNMPv3, gNMI, NETCONF, SSH CLI, Syslog, or a hybrid?
4. What is the expected production scale beyond the current 23 devices and current 964 observed ports?
5. Should application-level login/RBAC be required before STEP 1/2 design work, or treated as a later architecture finding?

## STOP

Per directive, stop after STEP 0 and wait for approval before STEP 1.
