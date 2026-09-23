# Ubuntu on-premises runtime

The native collector uses the same command policies, parsers, audit store, and protected change workflow as Windows. Select it explicitly with `NETWORK_AI_COLLECTOR=native`. Docker is not required.

Run the API as the dedicated `network-ai` system user with the supplied systemd unit, one Uvicorn worker, and Nginx proxying port 80 to `127.0.0.1:8000`. Keep existing hospital network access restrictions. The internal operations page is `http://172.16.1.20/operations`; external NAT addresses are managed separately by the IT team.

## Files and credentials

- Application: `/opt/network-ai-mvp/app`, root-owned, from a reviewed pushed Git commit.
- Python environment: `/opt/network-ai-mvp/venv`.
- State: `/var/lib/network-ai-mvp/data`; symlink `app/data` to this directory.
- Audit logs: `/var/lib/network-ai-mvp/logs`.
- Runtime settings: `/etc/network-ai-mvp/runtime.env`, root-readable only. Start from `deploy/linux/runtime.example`.
- Encrypted credentials: `/etc/credstore.encrypted/network-ai-<name>.cred`, root-readable only. Use `systemd-creds encrypt --name=<name>` and the unit's `LoadCredentialEncrypted` settings. Device payloads are JSON with `username` and `password`; the approval payload is the code alone. Never place plaintext payloads in source, shell arguments, logs, or application artifacts.
- systemd supplies decrypted credentials to the service in its private runtime credential directory. Windows DPAPI CLIXML files remain on Windows; they cannot be read directly on Linux.

Create `/etc/network-ai-mvp/collector-ready` only after actual collection validation. Enable and start `network-ai-mvp` and `nginx`; check `/health`, `/fault-monitor`, browser rendering, and journal errors. `systemctl restart network-ai-mvp` reloads application/configuration changes; only one polling instance may run. Service enablement provides boot startup, and `Restart=on-failure` handles process failure. The collection interval starts after each cycle; it is not streaming telemetry.

Port controls remain disabled in the example. In an authorized internal operational deployment, `NETWORK_AI_ENABLE_CHANGES=1` enables the existing per-action approval workflow. Do not test by shutting down a real port. Validate protected-port rejection and preview without executing a change. There is no per-user login/RBAC or browser-session unlock yet; see the handoff and backlog. Privilege escalation on a switch requires an explicit enable credential when its login lands at `>`.

Preserve existing redacted observations, monitoring SQLite state, and collection/change audits separately from the application artifact. Do not overwrite or discard history during later releases. Release provenance and rollback follow the [canonical workflow](../../.codex/rules/workflow.md).
