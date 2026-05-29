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

Credential files used during exploration:

- Cisco: `%USERPROFILE%\backbone_admin.cred.xml`
- Arista: `%USERPROFILE%\arista_kcl.cred.xml`

Do not commit or copy credential files into the project.

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
8. Natural-language report generation
9. Approval-based `shutdown/no shutdown` as the first controlled change feature
