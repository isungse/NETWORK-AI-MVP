# Project Status

## Goal

Provide a read-only network operations console that inventories devices, runs allowlisted diagnostics, stores redacted observations, and presents actionable port, endpoint, topology, and health information.

## Implemented Capabilities

- CSV-backed Cisco and Arista inventory with logical credential references.
- Read-only command plans enforced by backend policy.
- Windows PowerShell Telnet collection for explicitly configured legacy devices.
- Local redacted raw and parsed observation storage.
- Device dashboard, inventory, topology, Port Matrix, endpoint search, diagnostics, audit, and monitoring views.
- Port status, VLAN, speed/duplex, error-counter, MAC, ARP, and neighbor correlation.
- `link-diagnostics` analysis over the latest 10-minute observation window.
- Physical LINK Up to Line Protocol Up sequence detection.
- Current-port and other-port LINK/LINEPROTO event summaries.
- Vercel-hosted read-only reference UI.

## Durable Limitations

- Vercel cannot directly collect from private company-network device addresses.
- Local collection results are not automatically synchronized to Vercel.
- Production reference snapshots are not a live feed.
- Collection is manual; there is no persistent scheduler or polling service.
- The active collector uses Telnet and should be migrated to a secure transport.
- The API does not yet provide complete operator authentication and authorization for shared on-premises use.
- JSON and JSONL persistence is suitable for the MVP but not for concurrent production polling.

## Runtime Guidance

The canonical runtime boundary is documented in [`.codex/rules/architecture.md`](.codex/rules/architecture.md).

Git push, Vercel deployment, verification, rollback, and cleanup follow [`.codex/rules/workflow.md`](.codex/rules/workflow.md).

## Documentation Policy

This file records current product capability and durable limitations only. Do not add deployment IDs, process IDs, command transcripts, or session histories. Documentation routing follows [`.codex/rules/meta.md`](.codex/rules/meta.md).
