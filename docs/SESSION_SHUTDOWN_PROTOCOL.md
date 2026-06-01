# Session Shutdown Protocol

Use this checklist before ending a Network AI MVP development session.

## Purpose

Keep the next session recoverable without relying on chat history.

The shutdown checkpoint must capture:

- What changed: files, features, fixes.
- Why it changed: problem, requirement, or operational risk.
- How it was resolved: approach taken and alternatives considered.
- What failed or was discarded.
- Decisions made and the reasoning behind them.
- Remaining open issues and follow-up tasks.

## Required Checks

1. Inspect repository state.

```powershell
git status --short
git diff --stat
```

2. Run available verification.

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
```

If Monitoring UI changed:

```powershell
node --check src\network_ai_mvp\static\monitoring.js
```

3. Confirm no secrets were added.

```powershell
rg -n "password=|passwd|secret|\.cred\.xml|NETWORK_AI_CREDENTIAL|kcllove" .
```

Expected findings are documentation references, redaction tests, and credential environment variable names only. Plaintext device passwords must not appear.

4. Verify local API routes when server code changed.

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8012/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8012/
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8012/monitoring
```

5. Update recovery documents.

- `PROJECT_STATUS.md`
- `NEXT_TASK.md`
- `docs/network/NETWORK_AI_MVP_HANDOFF.md` when network facts or operational history changed.

6. Commit and push only after verification passes and the changed scope is intentional.

```powershell
git add <changed files>
git commit -m "<concise checkpoint message>"
git push origin main
```

7. Leave the server state explicit.

Record whether `http://127.0.0.1:8012/` is running. Do not assume it survives the next session.

## Current Session Checkpoint - 2026-06-01

### What Changed

Files and features:

- `src/network_ai_mvp/parsers.py`: added backend parsing utilities for interface status, descriptions, error counters, MAC table, ARP, and basic LLDP neighbor output.
- `src/network_ai_mvp/observations.py`: added local redacted raw and parsed latest observation storage under ignored `data/`.
- `src/network_ai_mvp/search.py`: added deterministic device/port/IP/MAC/reference-neighbor search.
- `src/network_ai_mvp/api.py`: added latest port APIs, search API, and one-click `POST /devices/{device_id}/check`.
- `src/network_ai_mvp/static/index.html`, `styles.css`, `app.js`: added Operations Search, Port Detail, and Inventory-top `CHECK` workflow.
- `tests/test_api.py`, `tests/test_parsers.py`, `tests/test_observations.py`: added coverage for search, observations, parsers, CHECK, and `/ask/plan` staying removed.
- `PROJECT_STATUS.md`, `NEXT_TASK.md`, `docs/network/NETWORK_AI_MVP_HANDOFF.md`: updated product direction and recovery notes.

### Why It Changed

- Natural-language Ask/Chat was too unreliable for operational network diagnostics and was deferred.
- The operator workflow for finding network faults was too complex when users had to understand command purposes first.
- The new target workflow is: select a device in Inventory, click `CHECK`, and review fixed read-only diagnostic results.
- Multi-port low-speed findings were unreadable when concatenated on one line.

### How It Was Resolved

- Kept the product deterministic and read-only.
- `CHECK` uses only fixed backend allowlisted purposes: `interfaces`, `endpoints`, `topology`, and `switching`.
- No user input becomes CLI.
- CHECK writes redacted raw/parsed observations on success.
- CHECK returns five operator-facing result rows:
  - low-speed negotiated port detection
  - high CRC/error/runts detection
  - uplink/LACP/trunk anomaly foundation
  - IP-MAC-Port correlation
  - documented topology vs live observed topology foundation
- CHECK detail strings now use one line per port and the UI preserves line breaks.

### Failed Or Discarded

- Ask/Chat active UI and `/ask/plan` endpoint remain removed.
- Browser plugin automation failed in the Windows sandbox; headless Chrome CDP was used for real UI verification.
- CHECK placement in Device Detail was discarded because it was hard to reach in narrower layouts.
- Full LACP/trunk/STP verdicts and topology mismatch verdicts are still foundations, not final diagnostics.

### Live Verification Notes

Read-only CHECK was executed against live devices during the session:

- `cisco-backbone`: CHECK success; 53 IP/MAC-correlated ports and 12 live-neighbor ports observed.
- `arista-b1f-3` / `B1F_ARI_101.249`: CHECK success; low-speed ports included `Et4` at `a-100M` and `Et27` at `a-10M`. Later user-visible output showed additional VLAN `101` low-speed ports.

Re-check live before taking operational action.

### Decisions

- Keep natural-language and LLM integration deferred.
- Keep CHECK fixed-purpose and allowlist-only.
- Show immature checks as `UNKNOWN` rather than guessing.
- Keep raw Collection Result visible.
- Do not add config/change commands.

### Verification

Latest completed verification:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
```

Results:

```text
Ran 38 tests
OK
```

HTTP checks:

- `GET /health`: 200
- `GET /`: 200
- `GET /monitoring`: 200
- `POST /ask/plan`: 404

Secret scan:

- Matches were expected documentation references, test redaction fixtures, credential environment variable names, and redaction code.
- No plaintext device password was found.

### Remaining Issues

- Add run-id history and recent change comparison.
- Add CHECK row links to Port Detail for affected ports.
- Add LACP/trunk/STP parsers and real anomaly verdicts.
- Add documented/reference topology vs live observed topology comparison.
- Classify known/expected low-speed endpoint links separately from abnormal low-speed links.
- Replace Telnet with SSH/API where possible.

### Server State

The local FastAPI server was left running:

```text
http://127.0.0.1:8012/
```

At shutdown, port `8012` was listening with the latest source loaded.

## Previous Session Checkpoint - 2026-05-30

### What Changed

Files and features:

- `inventory/backbone_neighbors.json`: added reference topology for Cisco backbone neighbors.
- `inventory/devices.csv`: added backbone-neighbor Cisco switches with management IPs as Telnet read-only inventory targets using logical credential ref `backbone_admin`.
- `src/network_ai_mvp/neighbors.py`: added typed loader and lookup helpers for backbone neighbor reference data.
- `src/network_ai_mvp/api.py`: added `/devices/{device_id}/neighbors`, `/monitoring`, and clearer PowerShell CLIXML error summarization.
- `src/network_ai_mvp/policy.py`: added separate `endpoints` Purpose for endpoint IP/MAC correlation; removed MAC/ARP from `baseline`.
- `scripts/backbone_telnet_readonly.ps1`: improved Telnet login handling for username/password and password-only prompts; fail fast on rejected credentials.
- `src/network_ai_mvp/static/index.html`, `styles.css`, `app.js`: added Connected Neighbors UI, endpoint summary rendering, Monitoring link, compact header layout, and improved collection result mirroring.
- `src/network_ai_mvp/static/monitoring.html`, `monitoring.js`: added standalone Monitoring page that mirrors the latest Collection Result through browser local storage.
- `tests/test_api.py`, `tests/test_inventory.py`, `tests/test_neighbors.py`, `tests/test_policy.py`: added coverage for neighbors, monitoring route, endpoint purpose, inventory changes, and readable PowerShell errors.

### Why It Changed

- Backbone neighbors discovered through CDP/LLDP needed to be visible in the UI without treating unmanaged/IP-less devices as safe collect targets.
- Operators needed to select neighbor devices from topology context and use the same Device Detail, Purpose, Command Plan, Diagnostics, and Collect workflow as inventory devices.
- Baseline collection became hard to read when endpoint IP/MAC data was appended to interface descriptions.
- Monitoring long raw results inside the main page was inconvenient.
- Cisco access-switch Telnet attempts could appear to hang when credentials were rejected or prompt style differed from the backbone switch.
- Header buttons and status labels were visually misaligned after the Monitoring page was added.

### How It Was Resolved

- Kept `devices.csv` for collect-capable devices and added `backbone_neighbors.json` for topology reference.
- Linked neighbor rows to inventory devices by management IP or hostname; rows now open the same detail/collect workflow as the inventory table.
- Left `Gi3/38` 9F computer room Cisco switch as a neighbor-only item because it has no management IP.
- Split endpoint IP/MAC correlation into Purpose `endpoints`.
- Rendered endpoint correlation as a dedicated `CONNECTED ENDPOINTS` section with one endpoint per line under each interface.
- Added `/monitoring` as a separate local page instead of a popup copy. The main UI publishes the latest rendered Collection Result to `localStorage`, and the Monitoring page mirrors it.
- Improved Telnet helper prompt detection and API error formatting so failed logins return quickly as `Login failed.` instead of CLIXML noise or long waits.
- Simplified header layout by hiding transient status text visually and aligning `Monitoring`/`Main UI` with the `READ-ONLY` badge.

### Failed Or Discarded

- Treating endpoint IP/MAC data as part of `baseline` was discarded because uplink ports produced long unreadable lines.
- `Open` and `Plan only` neighbor actions were discarded because they were unclear to operators; `Detail` and row-click behavior replaced them.
- Using existing `backbone_admin` and `arista_kcl.cred.xml` credentials for `172.16.102.250` failed; Telnet was reachable, but the stored credentials were rejected.
- Relying on double-click for neighbor rows was discarded; single-click now matches inventory table behavior.
- Browser automation checks were unreliable in the local Windows sandbox, so verification used HTTP checks, JavaScript syntax checks, and unit tests.

### Decisions

- Keep the MVP read-only. No arbitrary CLI or config commands were added.
- Keep topology reference data separate from collect inventory to avoid making IP-less or unverified devices look actionable.
- Use CLI-standard interface abbreviations in UI: `Te`, `Gi`, `Fa`, `Et`, `Po`, `Vl`.
- Use `localStorage` for Monitoring page synchronization because the MVP is local single-user and does not yet have collection run storage.
- Do not store plaintext credentials or user-provided passwords in source, logs, or docs.
- Keep Telnet only as a temporary MVP transport and continue to prioritize SSH/API migration later.

### Verification

Latest completed verification:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
```

Results:

```text
Ran 32 tests
OK
```

Latest pushed commit:

```text
2d7aea2 Add topology neighbors and monitoring view
```

### Remaining Issues

- Confirm correct Telnet credentials for Cisco access switches with the network management vendor.
- `172.16.102.250` accepts TCP/23 but rejects the tested stored credentials.
- `Gi3/38` 9F computer room Cisco switch has no management IP and remains neighbor-only.
- Endpoint IP/MAC correlation depends on both MAC table and ARP table being present on the collecting device; L2-only switches may not provide IP correlation.
- Local `localStorage` Monitoring mirror should eventually be replaced by persisted collection run storage.
- Telnet should be replaced with SSH/API transport before production use.
- Natural-language Ask panel and approval-based changes remain intentionally postponed.
