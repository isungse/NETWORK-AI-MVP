# STEP 6 Errdisable Real-Time Detection Checklist

Date: 2026-06-22
Scope: review checklist only. Codex implements after approval.

Purpose: detect errdisable events across all ports in near real time, surface the reason and recovery state to operators, and reflect the affected switch/link in the dashboard and topology. This step must remain read-only.

The directive spelling `errdiserable` is normalized here to `errdisable`.

## Current Code Anchors

- `src/network_ai_mvp/parsers.py:89` recognizes interface status tokens including `errdisabled`.
- `src/network_ai_mvp/observations.py:156` counts `disabled` and `errdisabled` ports in summary data.
- `src/network_ai_mvp/services/check.py:92` includes disabled/errdisabled ports in interface findings.
- `src/network_ai_mvp/static/monitoring.js:21` already uses `EventSource` for server-sent monitoring updates.
- No Syslog receiver, trap listener, errdisable recovery parser, or deduplication service is currently implemented.

No specific management IP, credential reference, or historical device value is printed in this checklist.

## Detection Path

Syslog first:
- [ ] Treat `%PM-4-ERR_DISABLE` and vendor-equivalent messages as the primary real-time signal.
- [ ] Add Cisco and Arista message parsers behind a backend service/module, not in frontend JavaScript.
- [ ] Normalize vendor-specific reason strings into stable reason codes such as `bpduguard`, `psecure_violation`, `link_flap`, `udld`, `storm_control`, `speed_misconfig`, and `unknown`.
- [ ] Store raw Syslog text only in a redacted/audited debug field if needed; normal UI uses normalized fields.

Polling fallback:
- [ ] Keep polling as a secondary path for devices without Syslog configured.
- [ ] Poll all devices and all ports for `errdisabled` state using read-only commands.
- [ ] Polling-detected events must carry `source: polling`.
- [ ] Syslog-detected events must carry `source: syslog`.
- [ ] If Syslog receiver is down, UI shows receiver status degraded while polling fallback continues.

Deduplication:
- [ ] Deduplicate the same incident when Syslog and polling both detect it.
- [ ] Dedup key should include device ID, interface, normalized reason, and a bounded time window.
- [ ] Repeated events after recovery are new incidents, not duplicates.

## Coverage Requirements

- [ ] Monitor every managed device from inventory; do not hardcode device names or addresses.
- [ ] Monitor every port, including uplinks, access ports, and port-channel members.
- [ ] Include unmanaged/reference neighbors only as context; incident ownership stays on the managed local device/port.
- [ ] Newly added inventory devices are included automatically after scheduler/collector refresh.
- [ ] Missing telemetry produces `unknown` or `stale`, not silent omission.

## Required Event Fields

Every errdisable event DTO must include:
- [ ] Stable event ID.
- [ ] Device ID and display label.
- [ ] Interface name, preferably normalized through the existing short-interface convention.
- [ ] Normalized reason code.
- [ ] Human-readable reason label.
- [ ] Event timestamp.
- [ ] Source: `syslog`, `polling`, or `manual_import`.
- [ ] Severity.
- [ ] Current state: active, recovered, suppressed, stale, or unknown.
- [ ] Last observed timestamp.
- [ ] Optional remote endpoint/link context when known.

Do not include:
- [ ] Credential references.
- [ ] Credential file paths.
- [ ] Passwords, tokens, or SNMP communities.
- [ ] Raw management IP values for normal users unless role policy explicitly allows reveal.

## Recovery Visibility

- [ ] Parse `show errdisable recovery` or vendor-equivalent read-only output.
- [ ] Show whether recovery is enabled for the detected reason.
- [ ] Show remaining recovery timer when available.
- [ ] If recovery is disabled, show "manual action required" without offering write commands.
- [ ] Track recovered state transitions.
- [ ] Track repeated auto-recovery and re-errdisable loops as flap behavior.
- [ ] Escalate severity when the same port repeatedly enters errdisable.

## Dashboard And Topology Behavior

Alarm feed:
- [ ] Push active errdisable incidents to the STEP 3 alarm feed.
- [ ] Alarm row includes timestamp, severity, device, port, reason, source, and state.
- [ ] Clicking the alarm opens the affected port detail.
- [ ] Recovery closes or updates the active alarm instead of creating confusing duplicates.

Topology:
- [ ] A switch with an active errdisable incident becomes warning or fault depending on policy.
- [ ] If the errdisabled port is an uplink, the STEP 5 edge health also changes.
- [ ] Stale detection remains visible; the affected node/link does not disappear.
- [ ] Reference-only topology edges are not allowed to claim live errdisable state without current evidence.

Port detail:
- [ ] Shows reason, source, first seen, last seen, recovery setting, remaining timer, and recurrence count.
- [ ] Shows read-only troubleshooting guidance by reason.
- [ ] Does not show a `no shutdown` or config-change action in this step.

## Read-Only Command Policy

- [ ] Any new commands for errdisable detection are read-only.
- [ ] Commands must be added to the existing allowlist/policy path before use.
- [ ] Blocked command regex must still reject config mode, shutdown/no-shutdown, reload, erase, delete, and write/copy operations.
- [ ] Detection commands must not accept arbitrary user-provided CLI strings.

Candidate read-only command families:
- [ ] Interface status.
- [ ] Interface counters.
- [ ] Errdisable recovery status.
- [ ] Logging buffer or Syslog event readback where supported and safe.
- [ ] Port-channel member status when the affected interface is bundled.

## State And Store Requirements

- [ ] Persist errdisable incidents separately from raw observations.
- [ ] Keep current active incidents as snapshot state.
- [ ] Keep incident history for recurrence analysis.
- [ ] Link incident history to device/port/uplink records.
- [ ] Store source and parser confidence.
- [ ] Use atomic writes/file locks in local mode, or a DB repository when migrated.

## Error Handling

- [ ] Syslog parser failures are captured as parser errors and do not break the receiver.
- [ ] Malformed messages do not crash the dashboard.
- [ ] Device polling timeout marks only that device stale/degraded.
- [ ] One device's failure does not block all-port monitoring.
- [ ] UI never freezes while waiting for errdisable detection.

## Security Requirements

- [ ] Redact secrets from raw Syslog/log text before audit or UI exposure.
- [ ] Apply app-level auth/RBAC before exposing operational event history broadly.
- [ ] Record which authenticated user viewed or acted on any future recovery workflow.
- [ ] Keep all recovery/change execution outside STEP 6.
- [ ] Require separate future approval for any write action such as interface reset.

## Tests Required For Codex Implementation

Backend tests:
- [ ] Cisco Syslog errdisable message parses into normalized event.
- [ ] Arista/vendor-equivalent message parses into normalized event.
- [ ] Unknown reason maps to `unknown` without crashing.
- [ ] Syslog + polling duplicate becomes one incident.
- [ ] Recovery event closes active incident.
- [ ] Repeated errdisable increments recurrence/flap count.
- [ ] Recovery parser extracts enabled causes and timer when present.
- [ ] Read-only policy allows only approved show/logging commands and blocks config commands.

Frontend/browser verification:
- [ ] Alarm feed updates without refresh.
- [ ] Node status changes when active incident arrives.
- [ ] Uplink edge status changes when the errdisabled port is an uplink.
- [ ] Port detail opens from alarm click.
- [ ] Stale receiver or polling failure is visible.

## Review Rejection Criteria

- [ ] Reject if implementation relies only on polling and ignores Syslog/trap path.
- [ ] Reject if reason is not shown.
- [ ] Reject if events are hardcoded to known devices or known ports.
- [ ] Reject if Syslog and polling create duplicate alarm rows for one incident.
- [ ] Reject if `no shutdown` or any config action is exposed in this step.
- [ ] Reject if stale/unreachable devices hide errdisable state.
- [ ] Reject if frontend parses raw Syslog/CLI text instead of rendering backend DTOs.

## STEP 6 Status

STEP 6 checklist is complete. It defines real-time errdisable detection criteria only and does not implement production code.
