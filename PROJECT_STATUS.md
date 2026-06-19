# Project Status

Last updated: 2026-06-19

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

The MVP is usable as a local FastAPI web application at `http://127.0.0.1:8013/` when the server is running.

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
- Purpose `port-endpoints` collects interface status, interface descriptions, MAC table, and ARP table to make per-port endpoint lookup easier.
- `port-endpoints` adds a backend-built `PORT ENDPOINT TRACE` section before raw stdout, showing interface, connected status, VLAN, speed, MAC, and correlated IP when available.
- Purpose `security-logs` collects Arista read-only operational/security log evidence with `show logging` and `show users`.
- The Telnet helper supports an optional encrypted enable credential path for approved privileged read-only checks. It is used only when explicitly supplied.
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

## Latest Session Checkpoint - 2026-06-19

### What Changed

- Added Arista read-only Purpose `security-logs`.
  - `terminal length 0`
  - `show logging`
  - `show users`
- Added optional `-EnableCredentialPath` support to `scripts/backbone_telnet_readonly.ps1`.
- Verified that `kcl` logs into Arista user exec mode first, and privileged read-only checks require enable.
- Confirmed SSH service is enabled on 2F Arista switches by TCP/22 and SSH banner.
- Ran read-only interface checks on 2F Arista switches for suspected link/port issues.
- Ran approved privileged read-only `show users` and `show logging` on 2F Arista switches.
- Updated shutdown/recovery documentation to keep the session handoff aligned with Network AI MVP only.

### Why It Changed

- The user reported a 2F endpoint that showed unplugged on a PC NIC while a cable tester showed no fault.
- The user asked whether Arista switch ports could be the cause.
- The user asked whether 2F Arista SSH was configured.
- The user asked whether there was evidence of external access or manipulation.
- `show users` required privileged mode, so enable credential support was needed for approved read-only auditing.

### Live Verification Notes

2F Arista SSH availability:

```text
172.16.105.249 / 4F_2F_ARI_105.249 / SSH-2.0-OpenSSH_7.8
172.16.105.247 / 2F_ARI_105.247    / SSH-2.0-OpenSSH_7.8
172.16.105.248 / 2F_ARI_105.248    / SSH-2.0-OpenSSH_7.8
```

2F Arista Et11 read-only check:

```text
172.16.105.249 Et11 connected  vlan=22  speed=a-1G  FCS=0 Rx=0 Runts=0 Tx=0
172.16.105.247 Et11 notconnect vlan=22  speed=auto  FCS=0 Rx=0 Runts=0 Tx=0
172.16.105.248 Et11 notconnect vlan=22  speed=auto  FCS=0 Rx=0 Runts=0 Tx=0
```

2F Arista suspected physical/link issue candidates from read-only interface checks:

```text
172.16.105.249 Et1  notconnect, historical FCS=368549, Rx=474389, Runts=105840
172.16.105.247 Et25 notconnect, historical FCS=427407, Rx=528487, Runts=101080
```

Other notable 2F high-error or low-speed observations:

```text
172.16.105.249 Et6  connected a-100M, FCS=7846661, Rx=9687745, Runts=1841084
172.16.105.249 Et16 connected a-1G,   FCS=802153,  Rx=993962,  Runts=191809
172.16.105.248 Et17 connected a-100M, FCS=880291,  Rx=1115148, Runts=234857
172.16.105.248 Et22 connected a-10M half, Rx=29278, Runts=29278
```

Privileged read-only log audit:

```text
172.16.105.249 show users: only kcl from 172.16.1.80, the audit session.
172.16.105.247 show users: only kcl from 172.16.1.80, the audit session.
172.16.105.248 show users: only kcl from 172.16.1.80, the audit session.
```

Filtered `show logging` evidence:

```text
External SSH/Telnet login evidence: not found in accessible device logs.
Configuration/change evidence: not found in accessible device logs.
copy/write/startup-config/running-config evidence: not found in accessible device logs.
username/account change evidence: not found in accessible device logs.
shutdown/no shutdown command evidence: not found in accessible device logs.
```

Important limitation:

```text
Persistent logging: disabled
Root login logging: disabled
```

Device buffer logs alone cannot prove long-term absence of access or manipulation. For strict audit, check central syslog and AAA/TACACS/RADIUS accounting.

### Verification

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
```

Result:

```text
Ran 40 tests
OK
```

Secret scan:

```powershell
rg -n "password=|passwd|secret|\.cred\.xml|NETWORK_AI_CREDENTIAL|kcllove" .
```

Result: expected documentation references, redaction tests, credential environment variable names, and redaction code only. No plaintext device password was found.

Secret scan:

```powershell
rg -n "password=|passwd|secret|\.cred\.xml|NETWORK_AI_CREDENTIAL|kcllove" .
```

Result: expected documentation references, redaction tests, credential environment variable names, and redaction code only. No plaintext device password was found.

### Open Follow-Ups

- Decide whether to migrate 2F Arista collection from Telnet to SSH now that SSH service is confirmed.
- Add first-class backend support for privileged read-only audit commands instead of only the PowerShell helper option.
- Add security-log parsing/reporting so login/config evidence is summarized inside the UI.
- Confirm central syslog and AAA accounting availability for stronger audit evidence.
- Re-check physical cabling/patch-panel mapping for `172.16.105.249 Et1` and `172.16.105.247 Et25` if they match the reported wall jack.

### Server State

The local FastAPI server is running:

```text
http://127.0.0.1:8013/
```

Health check result:

```json
{"status":"ok","mode":"read-only"}
```

## Previous Session Checkpoint - 2026-06-15

### What Changed

- No product code was changed during this session.
- The local FastAPI server was started for testing on `http://127.0.0.1:8013/`.
- `GET /health` returned `{"status":"ok","mode":"read-only"}`.
- The main UI returned `200 OK` and exposed the Inventory/Search UI and `/monitoring` link.
- The server process was stopped at session end by user request.

### Verification

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
```

Result:

```text
Ran 39 tests
OK
```

Secret scan:

```powershell
rg -n "password=|passwd|secret|\.cred\.xml|NETWORK_AI_CREDENTIAL|kcllove" .
```

Result: expected documentation references, redaction tests, credential environment variable names, and redaction code only. No plaintext device password was found.

### Server State

The local FastAPI server is stopped. `http://127.0.0.1:8013/health` returned connection refused after shutdown.

## Previous Session Checkpoint - 2026-06-02

### What Changed

- Added read-only Purpose `port-endpoints` for Cisco and Arista devices.
- Added backend `port_endpoint_trace` output for `POST /devices/{device_id}/collect/port-endpoints`.
- Added `PORT ENDPOINT TRACE` rendering in the Collection Result panel.
- Added `show interfaces status` to the new `port-endpoints` purpose so the trace includes port state, VLAN, and speed.
- Fixed Arista MAC address-table parsing so `Last Move ... ago` is not misread as an interface.
- Fixed interface description parsing so empty Arista descriptions are not displayed as `up`.
- Improved endpoint IP enrichment by using the latest stored raw observation that contains `show ip arp`, instead of assuming the newest file always contains ARP data.
- Added tests for `port-endpoints` command planning, Arista MAC parsing, and Et29 MAC-to-IP trace correlation.

### Why It Changed

- The existing `endpoints` purpose could collect MAC/ARP data, but it was not optimized for quickly answering: "Which IP and MAC are connected to this problematic port?"
- The Et29 investigation on `172.16.104.250` needed a concise port-centered view because raw baseline/endpoints output is too long for operational triage.
- Arista MAC table output includes aging text after the port column; the previous parser could treat the trailing word `ago` as a port.

### Live Verification Notes

Read-only live collection was executed against:

- `arista-1f-outpatient`
- Hostname/inventory: `4F_1F_ARI_104.259`
- Management IP: `172.16.104.250`

Confirmed current Et29 endpoint evidence at collection time:

```text
Et29  connected/a-1G  vlan=11
  - ip=172.16.11.9  mac=5c60.ba3c.725f
```

Context:

- User identified `Et29` as a high-error concern on `4F_1F_ARI_104.259 / 172.16.104.250`.
- Latest visible error evidence before this change:
  - `Et29`: connected, VLAN `11`, speed `a-1G`
  - `FCS=4348`, `Rx=4396`, `Runts=48`, `Tx=0`
- The local Arista ARP table did not directly show the Et29 endpoint IP.
- The endpoint IP was correlated through stored/latest backbone ARP evidence by MAC.
- This is collection-time evidence and must be re-checked live before operational action.

### Verification

```powershell
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
```

Result:

```text
Ran 39 tests
OK
```

API health check:

```text
GET http://127.0.0.1:8013/health
```

Result:

```json
{"status":"ok","mode":"read-only"}
```

### Open Follow-Ups

- Add a UI filter/search control inside `PORT ENDPOINT TRACE` so operators can jump directly to `Et29`, an IP, or a MAC inside large endpoint outputs.
- Move CHECK result rows to clickable Port Detail links for affected ports.
- Add endpoint pairing confidence labels when IP evidence comes from a different device's ARP observation.
- Add run-id history so IP/MAC correlation can cite the exact observation source and timestamp.
- Consider making `port-endpoints` the recommended workflow for single-port endpoint investigations.

## Previous Session Checkpoint - 2026-06-01

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
- Updated Cisco WS-C2960X backbone-neighbor inventory to use logical credential ref `cisco_access_admin`.
- Removed `show running-config | include ^hostname` from Cisco `baseline` because the confirmed access-switch account lands in user exec (`>`) and cannot run that command reliably.

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
- Cisco WS-C2960X access-neighbor `baseline` collection completed successfully with `cisco_access_admin` for all currently managed floor switches:
  - `cisco-9f-data` / `Data_9F_99.250` / `172.16.99.250`
  - `cisco-8f-data` / `Data_8F_88.250` / `172.16.88.250`
  - `cisco-7f-data` / `Data_7F_77.250` / `172.16.77.250`
  - `cisco-6f-data` / `Data_6F_66.250` / `172.16.66.250`
  - `cisco-5f-data` / `Data_5F_55.250` / `172.16.55.250`
  - `cisco-4f-data` / `Data_4F_44.250` / `172.16.44.250`
  - `cisco-3f-data` / `Data_3F_33.250` / `172.16.33.250`
  - `cisco-b1f-data` / `Data_B1F_101.251` / `172.16.101.251`
  - `cisco-b2f-data` / `Data_B2F_102.250` / `172.16.102.250`

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
- Using the older `backbone_admin` and `arista_kcl.cred.xml` credentials against `172.16.102.250` failed with `Login failed.` This was superseded by the confirmed `cisco_access_admin` credential.
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
- Cisco WS-C2960X access switches from `Data_3F_33.250` through `Data_B2F_102.250` are reachable with the confirmed `admin` credential stored as logical ref `cisco_access_admin`.

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

Latest local verification as of 2026-06-02:

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests
```

Result:

```text
Ran 39 tests
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
GET http://127.0.0.1:8013/health
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
- `POST /devices/cisco-9f-data/collect/baseline` succeeds with `cisco_access_admin`.

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
198b0d9 Confirm Cisco access switch credentials
```

Working tree at latest checkpoint:

- Not clean as of the 2026-06-02 port-endpoints update.
- Current uncommitted implementation/documentation changes include `port-endpoints`, `PORT ENDPOINT TRACE`, parser fixes, tests, and markdown updates.
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

The local FastAPI server is currently stopped.

```text
http://127.0.0.1:8013/
```

At the 2026-06-15 shutdown, port `8013` returned connection refused after stopping server process `48956`.

If needed, restart it with credential environment variables.

Example:

```powershell
$env:PYTHONPATH='src'
$env:NETWORK_AI_CREDENTIAL_BACKBONE_ADMIN="$env:USERPROFILE\backbone_admin.cred.xml"
$env:NETWORK_AI_CREDENTIAL_ARISTA_KCL="$env:USERPROFILE\arista_kcl.cred.xml"
$env:NETWORK_AI_CREDENTIAL_CISCO_ACCESS_ADMIN="$env:USERPROFILE\cisco_access_admin.cred.xml"
python -m uvicorn network_ai_mvp.api:create_app --factory --host 127.0.0.1 --port 8013
```
