# Next Task

## Immediate Next Step

Continue from the 2026-06-01 one-click CHECK checkpoint and commit the current implementation/documentation checkpoint if desired.

Latest pushed feature commit:

```text
2d7aea2 Add topology neighbors and monitoring view
```

Current documentation update:

- `docs/SESSION_SHUTDOWN_PROTOCOL.md`
- `PROJECT_STATUS.md`
- `NEXT_TASK.md`
- `docs/network/NETWORK_AI_MVP_HANDOFF.md`

Current uncommitted implementation scope:

- Backend parsed observations and local redacted storage.
- Deterministic Operations Search and Port Detail.
- Inventory-top one-click `CHECK` workflow.
- `POST /devices/{device_id}/check`.
- CHECK result display with one port per line for multi-port findings.

Recommended first commands next session:

```powershell
cd C:\Users\SPW\ai-project\Network-AI-MVP
git status --short
$env:PYTHONPATH='src'
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
```

Expected test result at this checkpoint: `Ran 38 tests, OK`.

## Recommended Development Order

1. Add CHECK result row links to Port Detail for affected ports.
2. Broaden persisted observation history beyond latest-only state and add run IDs.
3. Improve LLDP/CDP detail parsing for neighbor name, management IP, platform, and remote port.
4. Add parser-backed LACP/trunk/STP anomaly verdicts for CHECK.
5. Add documented-topology vs live-observed-topology mismatch checks.
6. Add reliable recent-change comparison once observation history exists.
7. Add daily morning health report foundation from stored observations.
8. Add expected-low-speed classification so known 100M/10M endpoint links can be separated from abnormal low-speed links.
9. Replace Telnet transport with SSH/API where possible.
10. Later revisit LLM as a bounded intent extraction and result summary layer.
11. Only after read-only stability, design approval-based single-interface `shutdown/no shutdown`.

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
Continue the port/device-centered operations console from the one-click CHECK checkpoint.

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

Implement:
1. Add CHECK result row links to Port Detail for affected ports.
2. Store each successful collection result:
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
3. Do not store credential paths or secrets.
4. Broaden local observation storage from latest-only to run-id history.
5. Improve parsers for the most important outputs:
   - Cisco/Arista LLDP detail
   - Cisco CDP detail
   - LACP/trunk/STP basics
6. Improve endpoint correlation in backend parsed observations:
   - pair IP and MAC per endpoint when possible
   - keep unmatched MAC or IP observations explicit
7. Improve CHECK diagnostics from parsed observations:
   - connected low-speed ports
   - disabled/errdisabled ports
   - high error counters
   - uplink-aware filtering where possible
8. Add daily health summary API and UI foundation.
9. Add documented/reference topology vs live observed topology comparison.
10. Add API endpoints:
   - GET /observations
   - GET /devices/{device_id}/observations/latest
   - GET /devices/{device_id}/diagnostics/latest
   - GET /devices/{device_id}/endpoints/latest
11. Update UI:
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

- The current server was intentionally left running and should not be stopped unless needed.
- Credential files are stored outside the repository:
  - `%USERPROFILE%\backbone_admin.cred.xml`
  - `%USERPROFILE%\arista_kcl.cred.xml`
- The server process needs credential environment variables to collect live device data:
  - `NETWORK_AI_CREDENTIAL_BACKBONE_ADMIN`
  - `NETWORK_AI_CREDENTIAL_ARISTA_KCL`
- Live collection should remain read-only and use only policy allowlisted purposes.
- One-click CHECK currently runs fixed allowlisted purposes only: `interfaces`, `endpoints`, `topology`, `switching`.
- `B1F_ARI_101.249` is inventory device `arista-b1f-3`.
- Latest live CHECK for `arista-b1f-3` found low-speed ports including `Et4` at `a-100M` and `Et27` at `a-10M`; user-visible later output showed additional VLAN 101 low-speed ports. Re-check live before operational action.
- Cisco access switches discovered from backbone neighbors are listed as Telnet targets, but credentials still need vendor confirmation.
- `172.16.102.250` currently rejects the tested stored credentials despite TCP/23 being reachable.

## High-Priority Follow-Ups

- Confirm whether `172.16.33.251 Ethernet52` is a real uplink errdisabled issue through read-only checks.
- Re-check `172.16.105.249 Ethernet6` error counter deltas.
- Keep `172.16.105.249 Ethernet1` and `Ethernet15` as historical operator-confirmed shutdowns until live state is rechecked.
- Add a known-risk refresh process so inventory/reference data does not drift from live observations.
- Confirm correct credential set for Cisco access switches.
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
