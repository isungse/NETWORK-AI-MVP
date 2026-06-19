# Network AI MVP Handoff

This document is the transfer note for continuing the network AI agent work from the current workspace into a new `Network-AI-MVP` project.

## Goal

Build an AI agent for company network operations.

Target progression:

1. Learn and document the company network.
2. Build a read-only diagnostic MVP.
3. Add approval-based change operations.
4. Eventually support controlled network maintenance actions.

## Current Recommendation

Use Python for the MVP.

Recommended stack:

- Backend/API: Python FastAPI
- Network automation: Scrapli or Netmiko
- Parallel inventory/collection: Nornir
- Database: PostgreSQL
- Knowledge base: Markdown files first, then database/vector search
- UI: Web UI or chat UI
- Secrets: Vault, Windows Credential Manager, or encrypted local credentials during MVP
- Audit: PostgreSQL plus append-only log files

## Safety Rules

- Start read-only.
- Use `show` commands only during MVP data collection.
- Do not let the LLM execute arbitrary CLI commands.
- Expose allowlisted tools/functions only.
- For changes, require explicit user approval.
- Generate rollback command before every change.
- Do not run `write memory` during quick verification tests unless explicitly approved.
- Log every command, result, target, requester, and timestamp.

## Product Direction Update - 2026-06-01

Natural-language Ask/Chat was prototyped and then removed from active product code.

Decision:

- Defer natural-language Ask/Chat for now.
- Rule-based natural-language intent mapping is not reliable enough for operational network diagnostics.
- Requests such as `BACKBONE-SW 연결 된 Gi3/24 포트를 확인하고 어떤 장비가 연결 된 지 알려주세요` require structured topology/endpoint evidence and target validation, not a guessed generic command purpose.

Current priority:

- Build a port/device-centered operations console.
- Add port search, device search, IP/MAC search, and a port detail page/panel.
- Persist structured read-only collection observations locally.
- Correlate interface status, LLDP/CDP, MAC, ARP, errors, speed, and VLAN per port.
- Add a `diagnose this port` button that uses only existing read-only command purposes.

Initial implementation status:

- Successful read-only collections can now write redacted raw output under `data/raw/` and parsed latest observations under `data/observations/`.
- The repository ignores `data/` because it is runtime state and may contain device output.
- Parsed port state includes interface status, VLAN, speed/duplex, descriptions, endpoint IP/MAC evidence, basic LLDP neighbor fields where available, and error counters.
- The UI has deterministic Operations Search and Port Detail panels.
- `Diagnose This Port` loads the existing allowlisted `interfaces` command plan and does not execute until the user clicks the existing `Collect` button.
- Recent changes intentionally shows a neutral no-history state until reliable observation history exists.
- One-click `CHECK` is available from the Inventory header after device selection.
- `CHECK` runs only backend-fixed read-only allowlisted purposes: `interfaces`, `endpoints`, `topology`, and `switching`.
- `CHECK` displays five operator-facing results:
  - low-speed negotiated port detection
  - high CRC/error/runts detection
  - uplink/LACP/trunk anomaly foundation
  - IP-MAC-Port correlation
  - documented topology vs live observed topology foundation
- CHECK multi-port findings are rendered one port per line for readability.

Latest live CHECK observations captured during the 2026-06-01 session:

- `cisco-backbone` CHECK completed successfully.
  - No parsed low-speed port found at collection time.
  - No parsed high error counter port found at collection time.
  - 53 ports had IP/MAC correlation.
  - 12 ports had live neighbor observations.
- `arista-b1f-3` / `B1F_ARI_101.249` CHECK completed successfully.
  - Low-speed negotiated ports included `Et4` at `a-100M` and `Et27` at `a-10M`.
  - User-visible later output showed additional VLAN `101` low-speed ports; re-check live before acting.

These observations are collection-time evidence, not permanent truth.

## Product Direction Update - 2026-06-02

The port/device-centered operations console was extended with a dedicated endpoint-trace purpose.

Decision:

- Keep `baseline` focused on basic device/interface facts.
- Keep `endpoints` for general endpoint collection.
- Add `port-endpoints` for operator triage when a specific problematic port needs IP/MAC identification.
- Keep all endpoint tracing read-only and allowlist-driven.

Implementation status:

- New Purpose: `port-endpoints`.
- Allowed commands:
  - `terminal length 0`
  - `show interfaces status`
  - `show interfaces description`
  - `show mac address-table`
  - `show ip arp`
- API response includes `port_endpoint_trace`.
- UI renders the trace as `PORT ENDPOINT TRACE` before raw stdout.
- The trace groups endpoint evidence by interface and shows:
  - interface
  - connected/admin state when available
  - VLAN
  - speed
  - description
  - MAC
  - correlated IPs
- Arista MAC-table parsing was fixed so aging text such as `1 day ... ago` is not treated as an interface.
- Endpoint IP enrichment can use recent stored ARP observations when the local switch ARP table does not contain the endpoint IP.

Latest live `port-endpoints` observation captured during the 2026-06-02 session:

- Device: `arista-1f-outpatient`
- Inventory hostname: `4F_1F_ARI_104.259`
- Management IP: `172.16.104.250`
- Problem port: `Et29`
- Port state at collection time: `connected`, VLAN `11`, speed `a-1G`
- Endpoint MAC: `5c60.ba3c.725f`
- Correlated endpoint IP: `172.16.11.9`

Operator context:

- `Et29` was investigated after high error counters were observed:
  - `FCS=4348`
  - `Rx=4396`
  - `Runts=48`
  - `Tx=0`
- The local Arista ARP output only showed gateway-related ARP entries.
- The endpoint IP was correlated by matching the Et29 MAC against recent stored ARP evidence, including backbone ARP observations.
- This is collection-time evidence, not permanent truth. Re-check live state before contacting the endpoint owner or taking operational action.

## Operational Audit Update - 2026-06-19

The 2F Arista devices were checked with read-only commands after user approval.

Devices:

- `arista-2f-outpatient` / `4F_2F_ARI_105.249` / `172.16.105.249`
- `arista-2f-1` / `2F_ARI_105.247` / `172.16.105.247`
- `arista-2f-2` / `2F_ARI_105.248` / `172.16.105.248`

SSH service check:

- All three devices accepted TCP/22.
- All three returned SSH banner `SSH-2.0-OpenSSH_7.8`.

Credential/privilege finding:

- `kcl` logs in to user exec first.
- Privileged read-only commands required enable.
- Enable credential was stored locally as `%USERPROFILE%\arista_enable.cred.xml`.
- The PowerShell Telnet helper now supports optional `-EnableCredentialPath`; use it only for explicitly approved privileged read-only checks.

Privileged read-only audit commands used:

```text
terminal length 0
show users
show logging
```

Current user evidence at collection time:

```text
172.16.105.249: only kcl from 172.16.1.80
172.16.105.247: only kcl from 172.16.1.80
172.16.105.248: only kcl from 172.16.1.80
```

Accessible log evidence:

- No external SSH/Telnet login evidence was found in accessible `show logging` output.
- No configuration/change evidence was found.
- No `copy`, `write memory`, running-config/startup-config evidence was found.
- No username/account-change evidence was found.
- No shutdown/no shutdown command evidence was found.

Audit limitation:

```text
Persistent logging: disabled
Root login logging: disabled
```

Device buffer logs alone cannot prove long-term absence of access or manipulation. For strict audit, check central syslog and AAA/TACACS/RADIUS accounting.

2F physical/link investigation:

- User reported a wall jack where a cable tester showed normal but a PC NIC showed unplugged; the same cable worked on another wall jack.
- Read-only interface checks suggest the issue is more likely physical path/switch-port mapping than PC NIC when the affected switch port remains `notconnect`.
- Most suspicious candidates if they map to the reported wall jack:
  - `172.16.105.249 / Et1`: `notconnect`, historical `FCS=368549`, `Rx=474389`, `Runts=105840`
  - `172.16.105.247 / Et25`: `notconnect`, historical `FCS=427407`, `Rx=528487`, `Runts=101080`
- Additional high-error/low-speed observations:
  - `172.16.105.249 / Et6`: connected `a-100M`, `FCS=7846661`, `Rx=9687745`, `Runts=1841084`
  - `172.16.105.249 / Et16`: connected `a-1G`, `FCS=802153`, `Rx=993962`, `Runts=191809`
  - `172.16.105.248 / Et17`: connected `a-100M`, `FCS=880291`, `Rx=1115148`, `Runts=234857`
  - `172.16.105.248 / Et22`: connected `a-10M half`, `Rx=29278`, `Runts=29278`

2F Et11 finding:

```text
172.16.105.249 Et11 connected  vlan=22 speed=a-1G FCS=0 Rx=0 Runts=0 Tx=0
172.16.105.247 Et11 notconnect vlan=22 speed=auto FCS=0 Rx=0 Runts=0 Tx=0
172.16.105.248 Et11 notconnect vlan=22 speed=auto FCS=0 Rx=0 Runts=0 Tx=0
```

No 2F Et11 error-counter issue was observed at collection time.

Future LLM direction:

- LLM may be used only for controlled intent extraction and result summarization.
- LLM must not generate executable CLI.
- Backend must validate device, interface, and purpose.
- Commands must always come from backend allowlists.
- User approval is still required before collection or any future change action.

## Known Network Facts

Primary detailed knowledge file:

- `docs/network/arista-10g-network-20241030-learning-data.md`

Important confirmed facts:

- Cisco backbone:
  - Hostname: `BACKBONE-SW`
  - Model: `WS-C4503-E`
  - Management IP: `172.16.1.1`
  - 1G/10G gateway context includes `172.17.17.1/24`
  - SSH failed from management PC; Telnet succeeded
- Arista 10G aggregation:
  - IP: `172.17.17.2`
  - Hostname: `9F_BB_ARI_17.2`
  - Model: `DCS-7050SX3-48YC8-F`
  - Cisco `Te1/3` maps to Arista `Et47`
  - Cisco `Te1/4` maps to Arista `Et48`
  - LACP bundle: `Po10`
- Firewall:
  - Model/name: `BLUEMAX NGF 300`
  - VLAN: `254`
  - Cisco VLAN name: `Firewall-Network`
  - VLAN 254 is not related to the Arista 10G network.
- Arista access:
  - `172.16.104.250`: 1F outpatient IP range, hostname `4F_1F_ARI_104.259`
  - `172.16.105.249`: 2F outpatient IP range, hostname `4F_2F_ARI_105.249`
  - B2F has no Arista equipment.

## Important Operational Events

- `172.16.105.249` / `4F_2F_ARI_105.249` / `Ethernet1` and `Ethernet15` were shutdown with explicit user approval.
- Operator confirmed both ports had `10M` speed issues and were shut down to identify which endpoint/terminal was connected.
- `write memory` was not executed.
- Before shutdown, `Ethernet1` was `connected`, VLAN `22`, `10M/full`.
- After shutdown, `Ethernet1` was `administratively down`.
- `Ethernet1` had significant historical errors:
  - `1139 link status changes`
  - `105840 runts`
  - `474389 input errors`
  - `368549 CRC`
  - `28213216 output discards`

Recovery command:

```text
enable
configure terminal
interface Ethernet1
no shutdown
end
show interfaces Ethernet1 status
```

Recovery for `Ethernet15`, if explicitly approved after live verification:

```text
enable
configure terminal
interface Ethernet15
no shutdown
end
show interfaces Ethernet15 status
```

## Current Helper Script

Existing script:

- `scripts/backbone_telnet_readonly.ps1`

It is currently used for Cisco/Arista Telnet sessions with encrypted local PowerShell credentials.

Current helper behavior:

- Handles username/password Telnet prompts.
- Handles password-only Telnet prompts.
- Fails fast with `Login failed.` when a device rejects credentials.
- API error handling converts PowerShell CLIXML error output into readable summaries.

Credential files used during exploration:

- Cisco: `%USERPROFILE%\backbone_admin.cred.xml`
- Arista: `%USERPROFILE%\arista_kcl.cred.xml`
- Cisco access switches: `%USERPROFILE%\cisco_access_admin.cred.xml`

Do not commit or copy credential files into the project.

## Latest UI/API Checkpoint - 2026-05-30

Implemented since the initial handoff:

- Local FastAPI UI at `/`.
- Monitoring page at `/monitoring`.
- Connected Neighbors table under Inventory.
- Backbone neighbor reference data in `inventory/backbone_neighbors.json`.
- Neighbor API: `GET /devices/{device_id}/neighbors`.
- Separate Purpose `endpoints` for endpoint IP/MAC correlation.
- Collection Result terminal-style rendering with color highlighting:
  - `connected`: green
  - `disabled`: red
- Public API device serializers hide credential refs.
- Audit/error redaction removes credential and secret-like values.

Important topology/reference additions:

- `9F_BB_ARI_17.2 / 172.17.17.2` is confirmed by LLDP as the Arista 10G core on Cisco `Te1/3` and `Te1/4`.
- `Po10` is the Cisco/Arista LACP bundle.
- Cisco backbone CDP/LLDP neighbors with management IPs are included in inventory as Telnet read-only targets.
- Cisco WS-C2960X access-neighbor credentials were confirmed by the management vendor and are mapped through logical credential ref `cisco_access_admin`.
- Read-only `baseline` collection succeeded for the managed Cisco access neighbors from `Data_9F_99.250` through `Data_B2F_102.250`.
- The Cisco access account lands in user exec (`>`), so Cisco `baseline` excludes `show running-config | include ^hostname`.
- `Gi3/38` is the 9F computer room Cisco switch. It has no management IP configured and remains neighbor-only.

Operational decision:

- Endpoint IP/MAC correlation is not part of `baseline`.
- Use Purpose `endpoints` to collect:
  - `show interfaces description`
  - `show mac address-table`
  - `show ip arp`
- The UI groups connected endpoint IP/MAC results by interface instead of appending long IP lists to interface description lines.

## Recommended Next Files In New Project

Suggested initial structure:

```text
Network-AI-MVP/
  docs/
    network/
      arista-10g-network-20241030-learning-data.md
      NETWORK_AI_MVP_HANDOFF.md
  scripts/
    backbone_telnet_readonly.ps1
  inventory/
    devices.csv
  src/
    network_ai_mvp/
```

## First MVP Feature Set

1. Device inventory
2. Read-only command runner
3. Interface status collector
4. LLDP/CDP topology collector
5. MAC/ARP correlation
6. Low-speed port detection
7. CRC/error/runts detection
8. Port/device-centered operations console
9. Structured collection observation storage
10. Controlled result summarization after backend validation
11. Approval-based `shutdown/no shutdown` as the first controlled change feature
