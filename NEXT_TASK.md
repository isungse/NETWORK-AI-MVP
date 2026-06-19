# Next Task

## Immediate Next Step

Continue from the 2026-06-19 2F Arista read-only audit checkpoint and commit the current implementation/documentation checkpoint if desired.

Latest 2026-06-19 session note: the local server is running on `http://127.0.0.1:8013/`. The session added Arista `security-logs` read-only purpose and optional enable support in the Telnet helper after explicit approval.

Latest pushed feature commit:

```text
198b0d9 Confirm Cisco access switch credentials
```

Current documentation update:

- `docs/SESSION_SHUTDOWN_PROTOCOL.md`
- `PROJECT_STATUS.md`
- `NEXT_TASK.md`
- `README.md`
- `docs/network/NETWORK_AI_MVP_HANDOFF.md`

Current uncommitted implementation scope:

- Backend parsed observations and local redacted storage.
- Deterministic Operations Search and Port Detail.
- Inventory-top one-click `CHECK` workflow.
- `POST /devices/{device_id}/check`.
- CHECK result display with one port per line for multi-port findings.
- New read-only Purpose `port-endpoints`.
- Backend `port_endpoint_trace` response for per-port IP/MAC lookup.
- Collection Result `PORT ENDPOINT TRACE` section.
- Arista MAC table parser fix for `Last Move ... ago` output.
- Et29 endpoint verification for `arista-1f-outpatient`.
- New Arista read-only Purpose `security-logs`.
- Optional encrypted enable credential support in `scripts/backbone_telnet_readonly.ps1`.
- 2F Arista SSH service verification.
- 2F Arista privileged read-only `show users` / `show logging` audit.

Recommended first commands next session:

```powershell
cd C:\Users\SPW\ai-project\Network-AI-MVP
git status --short
$env:PYTHONPATH='src'
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
```

Expected test result at this checkpoint: `Ran 40 tests, OK`.

## Recommended Development Order

1. Add UI/API summary for `security-logs` so login/config evidence is shown without reading raw logs.
2. Decide whether to migrate 2F Arista devices from Telnet to SSH transport now that SSH service is confirmed.
3. Add a filter/search control inside `PORT ENDPOINT TRACE` for direct port/IP/MAC lookup.
4. Add CHECK result row links to Port Detail for affected ports.
5. Broaden persisted observation history beyond latest-only state and add run IDs.
6. Add endpoint correlation source metadata so IP evidence can cite which device/run supplied ARP data.
7. Improve LLDP/CDP detail parsing for neighbor name, management IP, platform, and remote port.
8. Add parser-backed LACP/trunk/STP anomaly verdicts for CHECK.
9. Add documented-topology vs live-observed-topology mismatch checks.
10. Add reliable recent-change comparison once observation history exists.
11. Add daily morning health report foundation from stored observations.
12. Add expected-low-speed classification so known 100M/10M endpoint links can be separated from abnormal low-speed links.
13. Replace Telnet transport with SSH/API where possible.
14. Later revisit LLM as a bounded intent extraction and result summary layer.
15. Only after read-only stability, design approval-based single-interface `shutdown/no shutdown`.

## Natural-Language Ask/Chat Decision

Natural-language Ask/Chat was prototyped and deferred on 2026-06-01.

Reason:

- Rule-based natural-language intent mapping is not reliable enough for real network operations.
- Requests such as `BACKBONE-SW 연결 된 Gi3/24 포트를 확인하고 어떤 장비가 연결 된 지 알려주세요` need topology/endpoint evidence and explicit target validation, not a guessed generic command purpose.
- The active product should focus first on accurate structured network state and port/device-centered workflows.

Future LLM constraints:

- LLM may be used only for controlled intent extraction and result summarization.
- LLM must not generate executable CLI.
- Backend must validate device, interface, and purpose before planning.
- Commands must always come from backend allowlists.
- User approval is still required before collection or any future change action.

## Next Feature Prompt

Use this prompt for the next development session:

```text
Continue the Network-AI-MVP from the current checkpoint.

Before coding:
- Read PROJECT_STATUS.md.
- Read NEXT_TASK.md.
- Read README.md.
- Read docs/network/NETWORK_AI_MVP_HANDOFF.md.
- Read docs/network/arista-10g-network-20241030-learning-data.md.
- Inspect git status and preserve any uncommitted user changes.

Goal:
Continue the port/device-centered operations console from the one-click CHECK and port-endpoints checkpoint.

Scope:
- Read-only only.
- No shutdown/no shutdown.
- No write memory.
- No arbitrary CLI execution.
- Do not expose credentials.
- Do not add Supabase/PostgreSQL yet.
- Preserve the current terminal-style Collection Result UI.
- Preserve green connected and red disabled highlighting.
- Preserve the `/monitoring` page and Connected Neighbors UI.
- Preserve separate Purpose `endpoints`.
- Preserve separate Purpose `port-endpoints`.
- Preserve separate Purpose `security-logs`.
- Preserve the `PORT ENDPOINT TRACE` output before raw stdout.
- Preserve optional enable support only for explicitly approved privileged read-only checks.

Implement:
1. Add security-log summary output:
   - current users
   - login/logout evidence
   - config/change evidence
   - copy/write evidence
   - limitation note when persistent logging/root login logging is disabled
2. Add a filter/search control inside `PORT ENDPOINT TRACE` so a port such as `Et29`, an IP, or a MAC can be found without scanning long output.
3. Add CHECK result row links to Port Detail for affected ports.
4. Store each successful collection result:
   - timestamp
   - device_id
   - hostname
   - management_ip
   - purpose
   - commands
   - stdout
   - stderr
   - returncode
   - success
5. Do not store credential paths or secrets.
6. Broaden local observation storage from latest-only to run-id history.
7. Add source metadata to endpoint correlation:
   - local MAC table source device/run
   - ARP source device/run
   - timestamp
   - unmatched MAC/IP evidence
8. Improve parsers for the most important outputs:
   - Cisco/Arista LLDP detail
   - Cisco CDP detail
   - LACP/trunk/STP basics
9. Improve endpoint correlation in backend parsed observations:
   - pair IP and MAC per endpoint when possible
   - keep unmatched MAC or IP observations explicit
10. Improve CHECK diagnostics from parsed observations:
   - connected low-speed ports
   - disabled/errdisabled ports
   - high error counters
   - uplink-aware filtering where possible
11. Add daily health summary API and UI foundation.
12. Add documented/reference topology vs live observed topology comparison.
13. Add API endpoints:
   - GET /observations
   - GET /devices/{device_id}/observations/latest
   - GET /devices/{device_id}/diagnostics/latest
   - GET /devices/{device_id}/endpoints/latest
14. Update UI:
   - show parser-backed diagnostics separately from raw stdout
   - show connected endpoints as structured rows from backend parsed observations
   - show recent changes only after reliable history exists
   - keep raw stdout visible and copyable
   - keep the current visual direction

Tests:
- Parser fixture tests using saved sample text, not live devices.
- Storage path safety tests.
- API endpoint tests.
- Redaction tests.
- Full unittest suite must pass.

Verification:
- Run full tests.
- Run JS syntax check.
- Verify /health and static UI.
- Do not run live collection unless explicitly approved.
```

## Important Operational Notes

- The current server is running on `http://127.0.0.1:8013/` at the 2026-06-19 checkpoint.
- Credential files are stored outside the repository:
  - `%USERPROFILE%\backbone_admin.cred.xml`
  - `%USERPROFILE%\arista_kcl.cred.xml`
  - `%USERPROFILE%\cisco_access_admin.cred.xml`
  - `%USERPROFILE%\arista_enable.cred.xml`
- The server process needs credential environment variables to collect live device data:
  - `NETWORK_AI_CREDENTIAL_BACKBONE_ADMIN`
  - `NETWORK_AI_CREDENTIAL_ARISTA_KCL`
  - `NETWORK_AI_CREDENTIAL_CISCO_ACCESS_ADMIN`
- Live collection should remain read-only and use only policy allowlisted purposes.
- Enable credentials were approved and used only for privileged read-only Arista audit commands. Do not use enable for configuration changes without separate explicit approval.
- One-click CHECK currently runs fixed allowlisted purposes only: `interfaces`, `endpoints`, `topology`, `switching`.
- `port-endpoints` currently runs only read-only commands: `terminal length 0`, `show interfaces status`, `show interfaces description`, `show mac address-table`, and `show ip arp`.
- `security-logs` currently runs only read-only commands: `terminal length 0`, `show logging`, and `show users`.
- 2F Arista SSH is enabled and banners showed `SSH-2.0-OpenSSH_7.8` on `172.16.105.249`, `172.16.105.247`, and `172.16.105.248`.
- 2F Arista privileged `show users` showed only the audit session `kcl` from `172.16.1.80`.
- 2F Arista accessible logs did not show external login/config/write/account-change evidence, but persistent logging and root login logging are disabled.
- Latest read-only `port-endpoints` verification for `arista-1f-outpatient` found `Et29 -> mac=5c60.ba3c.725f -> ip=172.16.11.9`.
- The Et29 IP was correlated from stored/latest ARP evidence, not directly from the local Arista ARP table. Re-check live before acting.
- `B1F_ARI_101.249` is inventory device `arista-b1f-3`.
- Latest live CHECK for `arista-b1f-3` found low-speed ports including `Et4` at `a-100M` and `Et27` at `a-10M`; user-visible later output showed additional VLAN 101 low-speed ports. Re-check live before operational action.
- Cisco access switches discovered from backbone neighbors use logical credential ref `cisco_access_admin`.
- Cisco access-switch `baseline` collection succeeded for `Data_9F_99.250`, `Data_8F_88.250`, `Data_7F_77.250`, `Data_6F_66.250`, `Data_5F_55.250`, `Data_4F_44.250`, `Data_3F_33.250`, `Data_B1F_101.251`, and `Data_B2F_102.250`.
- Cisco access-switch account lands in user exec (`>`), so Cisco `baseline` intentionally excludes `show running-config | include ^hostname`.

## High-Priority Follow-Ups

- Confirm whether `172.16.33.251 Ethernet52` is a real uplink errdisabled issue through read-only checks.
- Re-check `172.16.105.249 Ethernet6` error counter deltas.
- Confirm wall-jack to switch-port mapping for the reported PC-NIC unplugged issue. Most suspicious candidates from read-only checks are `172.16.105.249 Et1` and `172.16.105.247 Et25`.
- Re-check `172.16.105.247 Ethernet34` because logs showed speed-misconfigured errdisable events.
- Re-check `172.16.104.250 Ethernet29` error counter deltas and endpoint ownership; latest endpoint evidence is `172.16.11.9 / 5c60.ba3c.725f`.
- Confirm central syslog and AAA/TACACS/RADIUS accounting availability for stronger access/manipulation audit.
- Keep `172.16.105.249 Ethernet1` and `Ethernet15` as historical operator-confirmed shutdowns until live state is rechecked.
- Add a known-risk refresh process so inventory/reference data does not drift from live observations.
- Keep `Gi3/38` neighbor-only until a management IP is configured.
- Decide when to migrate Telnet to SSH/API.

## Intentionally Postponed

- Natural-language chat UI. The rule-based prototype was removed from active code and deferred.
- Approval-based changes.
- Database integration.
- Supabase/PostgreSQL.
- Multi-user auth.
- Scheduled collectors.
- AI/RAG over historical observations.
