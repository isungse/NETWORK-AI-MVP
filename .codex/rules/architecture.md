# Deployment Architecture

## Runtime Roles

- Vercel hosts the read-only web UI and API for reviewed reference data.
- A Windows collector inside the company network performs device collection because it can reach private management addresses and use the existing PowerShell Telnet adapter.
- Vercel Firewall controls inbound access to the hosted application. It does not create an outbound route from Vercel to the company network.

## Network Boundary

Vercel Functions must not be assumed to reach RFC 1918 device addresses. Device credentials and direct Telnet or SSH sessions remain inside the company network. Do not expose the local collector API directly to the public internet.

## Current Data Flow

The deployed application can read a reviewed observation snapshot included in its deployment artifact. That snapshot is reference data, not a live feed. Local collections update the local data directory only.

## Target Data Flow

The preferred production architecture is:

1. A scheduled on-premises collector runs allowlisted read-only commands.
2. The collector redacts raw output and produces structured observations.
3. The collector sends observations outbound over authenticated HTTPS to a persistent ingest service.
4. The Vercel application reads persisted observations and displays freshness and source metadata.

The ingest endpoint must authenticate the collector, validate payloads, rate-limit requests, and avoid accepting arbitrary device commands.

## Security Constraints

- Never deploy plaintext credentials, CLIXML credential files, tokens, or environment files.
- Keep configuration-changing commands outside the collector allowlist.
- Treat Telnet as a temporary legacy transport and prefer SSH, API, SNMP, NETCONF, or gNMI where supported.
- Keep management addresses and raw CLI output limited to authorized operational users.

## Local Controlled Change Plane

- Configuration changes are disabled by default and must never run from the Vercel deployment.
- The on-premises API may expose only fixed, backend-validated single-interface `shutdown` and `no shutdown` plans when the local change gate and approval code are configured.
- A controlled change requires the locally configured approval code, live read-only precheck and postcheck, reviewed fixed commands with rollback guidance, and a dedicated audit record.
- Trunk ports, observed-neighbor ports, and other possible uplinks are not eligible for UI-driven changes.
- Quick port isolation and recovery modify running configuration only. They must not execute `write memory` or `copy running-config startup-config` implicitly.
- Keep the write executor isolated from the read-only command allowlist and reject every command shape except the fixed single-interface admin-state plan.

Git and Vercel operating procedures belong in [`workflow.md`](workflow.md).
