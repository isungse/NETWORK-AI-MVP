from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .models import Device, DiagnosticFinding
from .thresholds import (
    HIGH_ERROR_COUNTER_FIELDS,
    has_high_error_counters,
    high_error_counter_value,
    is_low_speed_connected_port,
)

DEFAULT_KNOWN_RISKS = Path(__file__).resolve().parents[2] / "inventory" / "known_risks.json"


def detect_low_speed_ports(
    observations: Iterable[object],
) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for item in observations:
        row = _port_mapping(item)
        if not row:
            continue
        if bool(row.get("is_uplink")) or not is_low_speed_connected_port(row):
            continue

        speed_mbps = row.get("speed_mbps")
        interface = str(row.get("interface") or "")
        findings.append(
            DiagnosticFinding(
                severity="warning",
                device_id=str(row.get("device_id") or ""),
                interface=interface,
                title="Low negotiated speed",
                evidence=(
                    f"{interface} is {row.get('status')} at {speed_mbps}Mb/s "
                    f"{row.get('duplex') or 'unknown-duplex'}"
                ),
                next_step="Check cable, endpoint NIC settings, and interface error counters.",
            )
        )
    return findings


def detect_error_counters(
    counters: Iterable[object],
) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []
    for item in counters:
        row = _normalized_error_mapping(item)
        if not row or not has_high_error_counters(row):
            continue

        reasons = [f"{field}={int(row.get(field) or 0)}" for field in HIGH_ERROR_COUNTER_FIELDS if int(row.get(field) or 0)]

        severity = "critical" if high_error_counter_value(row) >= 1000 else "warning"
        findings.append(
            DiagnosticFinding(
                severity=severity,
                device_id=str(row.get("device_id") or ""),
                interface=str(row.get("interface") or ""),
                title="Interface error counters present",
                evidence=", ".join(reasons),
                next_step="Re-check live counters, clear only with approval, then compare deltas after observation.",
            )
        )
    return findings


def summarize_findings(findings: Iterable[DiagnosticFinding]) -> str:
    ordered = sorted(findings, key=lambda item: _severity_rank(item.severity), reverse=True)
    if not ordered:
        return "No diagnostic findings from the supplied observations."

    lines = []
    for item in ordered:
        target = item.device_id if item.interface is None else f"{item.device_id} {item.interface}"
        lines.append(f"[{item.severity.upper()}] {target}: {item.title}. {item.evidence}")
        lines.append(f"Next: {item.next_step}")
    return "\n".join(lines)


def assess_device_risks(
    device: Device,
    *,
    audit_events: Iterable[dict[str, object]] = (),
    known_risks_path: str | Path = DEFAULT_KNOWN_RISKS,
) -> list[DiagnosticFinding]:
    findings: list[DiagnosticFinding] = []

    if device.access_method == "telnet":
        findings.append(
            DiagnosticFinding(
                severity="warning",
                device_id=device.device_id,
                interface=None,
                title="Temporary insecure access method",
                evidence="Inventory access_method is telnet.",
                next_step="Keep collection read-only and migrate this device to SSH or API access.",
            )
        )
    elif device.access_method == "unknown":
        findings.append(
            DiagnosticFinding(
                severity="warning",
                device_id=device.device_id,
                interface=None,
                title="Access method not verified",
                evidence="Inventory access_method is unknown.",
                next_step="Verify management reachability and transport before enabling collection.",
            )
        )

    if "hostname/ip mismatch" in device.notes.lower():
        findings.append(
            DiagnosticFinding(
                severity="warning",
                device_id=device.device_id,
                interface=None,
                title="Hostname and management IP mismatch",
                evidence=device.notes,
                next_step="Confirm live hostname and update inventory or device naming when approved.",
            )
        )

    findings.extend(_known_risk_findings(device, known_risks_path))

    recent_failures = _recent_failed_events(device.device_id, audit_events)
    if recent_failures:
        findings.append(
            DiagnosticFinding(
                severity="warning",
                device_id=device.device_id,
                interface=None,
                title="Recent collection failures",
                evidence=f"{recent_failures} failed audit event(s) recorded for this device.",
                next_step="Check credential mapping, access method, and device reachability before retrying.",
            )
        )

    if not findings:
        findings.append(
            DiagnosticFinding(
                severity="info",
                device_id=device.device_id,
                interface=None,
                title="No pre-collection risk flags",
                evidence="Inventory and recent audit history do not show a known local risk flag.",
                next_step="Run allowlisted read-only collection before making operational conclusions.",
            )
        )
    return findings


def _severity_rank(severity: str) -> int:
    return {"info": 1, "warning": 2, "critical": 3}.get(severity, 0)


def _recent_failed_events(device_id: str, audit_events: Iterable[dict[str, object]]) -> int:
    count = 0
    for event in audit_events:
        if event.get("device_id") == device_id and event.get("success") is False:
            count += 1
    return count


def _known_risk_findings(device: Device, known_risks_path: str | Path) -> list[DiagnosticFinding]:
    records = _load_known_risks(known_risks_path)
    findings: list[DiagnosticFinding] = []
    for record in records:
        if record.get("device_id") != device.device_id:
            continue
        classification = _risk_classification(record.get("source_classification"))
        evidence = str(record.get("evidence") or "")
        evidence_with_scope = f"{_classification_label(classification)}: {evidence}"
        findings.append(
            DiagnosticFinding(
                severity=_risk_severity(record.get("severity")),
                device_id=device.device_id,
                interface=_optional_string(record.get("interface")),
                title=str(record.get("title") or "Known device risk"),
                evidence=evidence_with_scope,
                next_step=str(record.get("next_step") or "Use read-only collection to verify current state."),
            )
        )
    return findings


def _load_known_risks(path: str | Path) -> list[dict[str, object]]:
    risk_path = Path(path)
    if not risk_path.exists():
        return []
    with risk_path.open(encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _risk_severity(value: object) -> str:
    severity = str(value or "warning").lower()
    if severity in {"info", "warning", "critical"}:
        return severity
    return "warning"


def _risk_classification(value: object) -> str:
    classification = str(value or "reference").lower()
    if classification in {"historical", "reference", "live"}:
        return classification
    return "reference"


def _classification_label(classification: str) -> str:
    if classification == "live":
        return "Live observation"
    if classification == "historical":
        return "Historical reference - Not live truth"
    return "Reference data - Not live truth"


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _port_mapping(item: object) -> Mapping[str, Any] | None:
    if isinstance(item, Mapping):
        return item
    if is_dataclass(item) and not isinstance(item, type):
        return asdict(item)
    return None


def _normalized_error_mapping(item: object) -> dict[str, Any] | None:
    row = _port_mapping(item)
    if not row:
        return None
    normalized = dict(row)
    if "fcs_errors" not in normalized and "crc_errors" in normalized:
        normalized["fcs_errors"] = normalized.get("crc_errors")
    if "rx_errors" not in normalized and "input_errors" in normalized:
        normalized["rx_errors"] = normalized.get("input_errors")
    if "tx_errors" not in normalized and "output_discards" in normalized:
        normalized["tx_errors"] = normalized.get("output_discards")
    return normalized
