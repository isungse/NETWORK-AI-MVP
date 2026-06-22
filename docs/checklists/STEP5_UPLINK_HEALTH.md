# STEP 5 Uplink Health Checklist

Date: 2026-06-22
Scope: review checklist only. Codex implements after approval.

Purpose: every switch-to-switch edge must communicate the health of the underlying uplink. Operators should be able to see degraded uplinks from the topology without opening raw command output.

## Uplink Definition

- [ ] An uplink is an interface that connects one managed switch to another managed or known network device.
- [ ] Uplink identity is derived from CDP/LLDP first.
- [ ] External topology config may mark uplinks only as an interim fallback.
- [ ] Port-channel logical interfaces and member interfaces are modeled together.
- [ ] Unknown or unmanaged remote endpoints remain visible with lower confidence.

## Required Health Metrics

Interface state:
- [ ] Admin status.
- [ ] Operational status.
- [ ] Last status change when available.
- [ ] Stale/no-sample status.

Utilization:
- [ ] Inbound Mbps.
- [ ] Outbound Mbps.
- [ ] Inbound utilization percent.
- [ ] Outbound utilization percent.
- [ ] Link capacity used for percent calculation.

Error/discard rates:
- [ ] CRC/FCS error rate.
- [ ] Input error rate.
- [ ] Output error rate.
- [ ] Input discard rate.
- [ ] Output discard rate.
- [ ] Counter reset detection.

Port-channel/LACP:
- [ ] Bundle admin/oper status.
- [ ] Member interface status.
- [ ] Minimum active member threshold.
- [ ] Split/partial bundle warning.

## State And History Requirements

- [ ] Health uses at least two timestamped samples for rate calculations.
- [ ] Absolute counters alone are not enough for production severity.
- [ ] Missing previous sample yields `unknown` or `warming_up`, not false normal.
- [ ] Counter decrease is treated as reset/wrap and does not produce a false spike.
- [ ] Last sample timestamp is included in edge data.
- [ ] Device timeout marks affected uplinks stale/down depending on known last state.

## Edge Rendering Contract

Color:
- [ ] Green = normal.
- [ ] Yellow = warning/degraded.
- [ ] Red = fault/down/high error.
- [ ] Gray = stale/unreachable/unknown.

Thickness or dash:
- [ ] Thickness may represent utilization or capacity.
- [ ] Dash style may represent stale/reference-only state.
- [ ] The mapping is centralized and testable.

Interaction:
- [ ] Hover shows concise metrics: local/remote interface, status, utilization, errors/discards, last sample.
- [ ] Click opens full uplink detail.
- [ ] Related alarms are visible from the edge detail view.

Alarm integration:
- [ ] Threshold crossing creates or updates an alarm in the alarm feed.
- [ ] Alarm includes device, interface, remote endpoint, severity, metric, current value, threshold, and timestamp.
- [ ] Recovery/clear events update the existing alarm state instead of creating confusing duplicates.

## Suggested Severity Policy

Fault/red:
- [ ] Oper down while admin up on a managed uplink.
- [ ] Port-channel has no active members.
- [ ] Remote side unreachable/stale beyond allowed timeout.
- [ ] Error/discard rate exceeds critical threshold.

Warning/yellow:
- [ ] Utilization exceeds warning threshold.
- [ ] Error/discard rate exceeds warning threshold.
- [ ] Port-channel has degraded member count but still forwards.
- [ ] Neighbor mismatch or topology confidence degraded.

Stale/gray:
- [ ] No recent sample.
- [ ] Device collection failed.
- [ ] Link is reference-only and not confirmed by live discovery.

Normal/green:
- [ ] Oper/admin up.
- [ ] Utilization within threshold.
- [ ] Error/discard rates within threshold.
- [ ] Port-channel members healthy if applicable.

## Backend Contract For Codex

- [ ] Add an uplink health service separate from route handlers.
- [ ] Input comes from normalized topology edges plus observation history.
- [ ] Output DTO is attached to each topology edge.
- [ ] DTO includes `status`, `severity`, `metrics`, `thresholds`, `last_sample_at`, `source`, and `stale_reason`.
- [ ] Tests cover down link, high utilization, high error rate, stale data, missing sample, counter reset, and port-channel degradation.

## Frontend Contract For Codex

- [ ] Edge style derives only from uplink health DTO.
- [ ] No inline metric thresholds in UI code.
- [ ] Edge detail panel is available from topology click.
- [ ] Alarm feed updates when edge severity changes.
- [ ] Stale links remain rendered.

## Review Rejection Criteria

- [ ] Reject if edge color is based only on static reference status.
- [ ] Reject if error counters are treated only as absolute values.
- [ ] Reject if stale links disappear.
- [ ] Reject if port-channel members are ignored where bundle information exists.
- [ ] Reject if threshold crossing does not appear in the alarm feed.

## STEP 5 Status

STEP 5 checklist is complete. It defines uplink health behavior and rendering criteria only.
