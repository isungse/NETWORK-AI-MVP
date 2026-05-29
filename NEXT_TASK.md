# Next Task

## Immediate Next Step

Commit the stable UI checkpoint changes, then continue with the next feature phase.

Current uncommitted changes:

- Collection Result renders terminal-style stdout rather than escaped JSON.
- Collection Result highlights only:
  - `connected` in green
  - `disabled` in red
- `PROJECT_STATUS.md` and `NEXT_TASK.md` were added for session continuity.

Recommended first commands next session:

```powershell
cd C:\Users\SPW\ai-project\Network-AI-MVP
git status --short
$env:PYTHONPATH='src'
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
```

If the UI should remain the accepted direction, commit and push:

```powershell
git add src/network_ai_mvp/static/app.js src/network_ai_mvp/static/styles.css PROJECT_STATUS.md NEXT_TASK.md
git commit -m "Improve collection result terminal display"
git push
```

## Recommended Development Order

1. Add a read-only observation storage pipeline.
2. Add parser-backed diagnostics.
3. Add natural-language Ask panel that maps requests to safe read-only intents.
4. Add collection run history and raw output retrieval by run id.
5. Replace Telnet transport with SSH/API where possible.
6. Only after read-only stability, design approval-based single-interface `shutdown/no shutdown`.

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
Add local read-only observation storage and parser-backed diagnostics.

Scope:
- Read-only only.
- No shutdown/no shutdown.
- No write memory.
- No arbitrary CLI execution.
- Do not expose credentials.
- Do not add Supabase/PostgreSQL yet.
- Preserve the current terminal-style Collection Result UI.
- Preserve green connected and red disabled highlighting.

Implement:
1. Create a local data layout:
   - data/raw/
   - data/observations/
   - data/audit/ if needed, or keep logs/ if already established.
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
4. Add parsers for the most important outputs:
   - Cisco `show interfaces status`
   - Arista `show interfaces status`
   - Cisco/Arista interface error counters
   - LLDP neighbor basics
5. Add diagnostics from parsed observations:
   - connected low-speed ports
   - disabled/errdisabled ports
   - high error counters
   - uplink-aware filtering where possible
6. Add API endpoints:
   - GET /observations
   - GET /devices/{device_id}/observations/latest
   - GET /devices/{device_id}/diagnostics/latest
7. Update UI:
   - show parsed findings separately from raw stdout
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

## High-Priority Follow-Ups

- Confirm whether `172.16.33.251 Ethernet52` is a real uplink errdisabled issue through read-only checks.
- Re-check `172.16.105.249 Ethernet6` error counter deltas.
- Keep `172.16.105.249 Ethernet1` and `Ethernet15` as historical operator-confirmed shutdowns until live state is rechecked.
- Add a known-risk refresh process so inventory/reference data does not drift from live observations.
- Decide when to migrate Telnet to SSH/API.

## Intentionally Postponed

- Natural-language chat UI.
- Approval-based changes.
- Database integration.
- Supabase/PostgreSQL.
- Multi-user auth.
- Scheduled collectors.
- AI/RAG over historical observations.
