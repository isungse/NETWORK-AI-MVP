# Prioritized Backlog

## Highest Priority

1. Add an on-premises scheduled collector that runs allowlisted diagnostics at controlled intervals.
2. Add authenticated outbound synchronization from the on-premises collector to persistent storage used by the Vercel UI.
3. Display observation freshness, collection source, and last-success/last-failure status throughout the UI.
4. Refresh and select the newest link-event port automatically after a successful `link-diagnostics` run.

## Reliability and Security

1. Replace Telnet with SSH, API, SNMP, NETCONF, or gNMI adapters where devices support them.
2. Add authenticated operator identity and RBAC before sharing the local approval-code change controls beyond the trusted operations workstation.
3. Move concurrent observation and audit storage to a transactional database.
4. Add queue backpressure, per-device retry/backoff, timeouts, and stale-state handling.
5. Keep arbitrary CLI outside the MVP and retain the fixed-command, local-only boundary for configuration changes.

## Diagnostics

1. Expand parser-backed LACP, trunk, STP, errdisable, and link-flap assessments.
2. Improve endpoint evidence provenance across MAC and ARP sources.
3. Add topology mismatch detection between reference and live CDP/LLDP state.
4. Add scheduled health summaries based on persisted observations.

## Workflow

Use [`.codex/rules/workflow.md`](.codex/rules/workflow.md) for all GitHub and Vercel publication work. Update this backlog only when priorities change; do not append session logs or completed deployment records.
