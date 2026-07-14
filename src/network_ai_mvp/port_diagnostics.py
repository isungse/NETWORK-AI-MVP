from __future__ import annotations

import ipaddress
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .observations import find_latest_port
from .parsers import short_interface_name


LINK_EVENT_RE = re.compile(
    r"^(?P<month>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<year>\d{4})\s+"
    r"(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<zone>[A-Z]+):\s+"
    r"%(?P<family>LINK|LINEPROTO)-\d+-UPDOWN:\s+"
    r"(?:Line protocol on )?Interface\s+(?P<interface>[^,]+),\s+changed state to\s+(?P<state>\w+)",
    re.MULTILINE,
)
DIAGNOSTIC_WINDOW_MINUTES = 10


def build_port_connection_diagnostic(
    base_dir: str | Path,
    *,
    device_id: str,
    interface: str,
    window_minutes: int = DIAGNOSTIC_WINDOW_MINUTES,
) -> dict[str, Any]:
    port = find_latest_port(base_dir, device_id, interface)
    if not port:
        return {
            "data_available": False,
            "device_id": device_id,
            "interface": short_interface_name(interface),
            "message": "No stored parsed observation for this port yet.",
            "port": None,
            "history": [],
            "link_events": [],
        }

    history = _read_port_history(base_dir, device_id, interface)
    all_link_events, observation_time = _read_link_event_context(base_dir, device_id)
    target = short_interface_name(interface).lower()
    window_minutes = max(1, min(int(window_minutes), 60))
    window_end = observation_time or _latest_event_time(all_link_events)
    window_start = window_end - timedelta(minutes=window_minutes) if window_end else None
    recent_events = [
        event
        for event in all_link_events
        if _event_in_window(event, window_start=window_start, window_end=window_end)
    ]
    link_events = [
        event
        for event in recent_events
        if short_interface_name(str(event.get("interface") or "")).lower() == target
    ]
    other_port_events = [
        event
        for event in recent_events
        if short_interface_name(str(event.get("interface") or "")).lower() != target
    ]
    event_sequence = _link_up_sequence(link_events)
    status = str(port.get("status") or "unknown").lower()
    endpoint_ips = list(port.get("endpoint_ips") or [])
    endpoint_macs = list(port.get("endpoint_macs") or [])
    total_errors = sum(
        int(port.get(key) or 0)
        for key in ("fcs_errors", "align_errors", "symbol_errors", "rx_errors", "runts", "giants", "tx_errors")
    )
    if status in {"connected", "up"} and endpoint_ips:
        severity = "normal"
        conclusion = "Link is up and the endpoint IP/MAC is learned on this port."
    elif status in {"connected", "up"}:
        severity = "warning"
        conclusion = "Link is up, but no endpoint IP is currently correlated with this port."
    else:
        severity = "critical"
        conclusion = "Physical or operational link is not up in the latest port observation."

    return {
        "data_available": True,
        "device_id": device_id,
        "interface": port.get("interface") or short_interface_name(interface),
        "severity": severity,
        "conclusion": conclusion,
        "port": port,
        "endpoint_ips": endpoint_ips,
        "endpoint_macs": endpoint_macs,
        "total_errors": total_errors,
        "history": history[-20:],
        "link_events": link_events[-20:],
        "last_link_event": link_events[-1] if link_events else None,
        "event_sequence": event_sequence,
        "diagnostic_window": {
            "minutes": window_minutes,
            "start": window_start.isoformat() if window_start else None,
            "end": window_end.isoformat() if window_end else None,
        },
        "other_port_events": other_port_events[-20:],
        "other_port_event_count": len(other_port_events),
        "other_port_assessment": (
            f"No other port LINK/LINEPROTO events were observed in the latest {window_minutes}-minute window."
            if not other_port_events
            else f"{len(other_port_events)} LINK/LINEPROTO event(s) on other ports were observed in the latest {window_minutes}-minute window."
        ),
        "ping_available": bool(endpoint_ips),
    }


def build_recent_link_diagnostic(
    base_dir: str | Path,
    *,
    device_id: str,
    window_minutes: int = DIAGNOSTIC_WINDOW_MINUTES,
) -> dict[str, Any]:
    window_minutes = max(1, min(int(window_minutes), 60))
    all_link_events, observation_time = _read_link_event_context(base_dir, device_id)
    window_end = observation_time or _latest_event_time(all_link_events)
    window_start = window_end - timedelta(minutes=window_minutes) if window_end else None
    recent_events = [
        event
        for event in all_link_events
        if _event_in_window(event, window_start=window_start, window_end=window_end)
    ]
    if not recent_events:
        return {
            "data_available": False,
            "device_id": device_id,
            "interface": None,
            "message": f"No LINK/LINEPROTO event was observed in the latest {window_minutes}-minute window.",
            "diagnostic_window": {
                "minutes": window_minutes,
                "start": window_start.isoformat() if window_start else None,
                "end": window_end.isoformat() if window_end else None,
            },
        }
    return build_port_connection_diagnostic(
        base_dir,
        device_id=device_id,
        interface=str(recent_events[-1]["interface"]),
        window_minutes=window_minutes,
    )


def ping_target(
    target_ip: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    address = ipaddress.ip_address(target_ip)
    if address.is_loopback or address.is_multicast or address.is_unspecified:
        raise ValueError("Unsafe ping target.")

    command = (
        ["ping", "-n", "4", "-w", "1000", str(address)]
        if os.name == "nt"
        else ["ping", "-c", "4", "-W", "1", str(address)]
    )
    completed = runner(
        command,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    replies = len(re.findall(r"(?:TTL[=<]\s*\d+|bytes from)", output, flags=re.IGNORECASE))
    if completed.returncode == 0 and replies == 0:
        replies = 4
    replies = min(replies, 4)
    loss = round((4 - replies) / 4 * 100)
    success = completed.returncode == 0 and replies > 0
    return {
        "target_ip": str(address),
        "success": success,
        "packets_sent": 4,
        "packets_received": replies,
        "packet_loss_percent": loss,
        "summary": (
            f"Ping successful: {replies}/4 replies, {loss}% loss."
            if success
            else f"Ping failed: {replies}/4 replies, {loss}% loss."
        ),
    }


def _read_port_history(base_dir: str | Path, device_id: str, interface: str) -> list[dict[str, Any]]:
    observation_dir = Path(base_dir).resolve() / "observations" / device_id
    target = short_interface_name(interface).lower()
    history: list[dict[str, Any]] = []
    previous_status = None
    if not observation_dir.exists():
        return history

    for path in sorted(observation_dir.glob("*.json")):
        if path.name in {"latest.json", "index.json"}:
            continue
        payload = _read_json(path)
        if not payload:
            continue
        match = next(
            (
                port
                for port in payload.get("ports") or []
                if short_interface_name(str(port.get("interface") or "")).lower() == target and port.get("status")
            ),
            None,
        )
        if not match:
            continue
        status = str(match.get("status"))
        if status == previous_status:
            continue
        previous_status = status
        history.append(
            {
                "timestamp": payload.get("timestamp"),
                "status": status,
                "vlan": match.get("vlan"),
                "speed": match.get("speed"),
                "duplex": match.get("duplex"),
                "purpose": payload.get("purpose"),
            }
        )
    return history


def _read_link_event_context(
    base_dir: str | Path,
    device_id: str,
) -> tuple[list[dict[str, Any]], datetime | None]:
    raw_dir = Path(base_dir).resolve() / "raw" / device_id
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    latest_observation_time = None
    if not raw_dir.exists():
        return [], None

    for path in sorted(raw_dir.glob("*.json")):
        payload = _read_json(path)
        if not payload:
            continue
        payload_time = _parse_iso_datetime(payload.get("timestamp"))
        if payload_time and (latest_observation_time is None or payload_time > latest_observation_time):
            latest_observation_time = payload_time
        stdout = str(payload.get("stdout") or "")
        for match in LINK_EVENT_RE.finditer(stdout):
            event_interface = short_interface_name(match.group("interface").strip())
            timestamp = _event_timestamp(match)
            event = {
                "timestamp": timestamp,
                "interface": event_interface,
                "event": match.group("family").lower(),
                "state": match.group("state").lower(),
                "message": match.group(0).strip(),
            }
            unique[(timestamp, event_interface.lower(), event["event"], event["state"])] = event
    return sorted(unique.values(), key=lambda item: item["timestamp"]), latest_observation_time


def _latest_event_time(events: list[dict[str, Any]]) -> datetime | None:
    values = [_parse_iso_datetime(event.get("timestamp")) for event in events]
    return max((value for value in values if value is not None), default=None)


def _event_in_window(
    event: dict[str, Any],
    *,
    window_start: datetime | None,
    window_end: datetime | None,
) -> bool:
    timestamp = _parse_iso_datetime(event.get("timestamp"))
    if timestamp is None or window_start is None or window_end is None:
        return False
    return window_start <= timestamp <= window_end


def _link_up_sequence(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for physical in reversed(events):
        if physical.get("event") != "link" or physical.get("state") != "up":
            continue
        physical_time = _parse_iso_datetime(physical.get("timestamp"))
        if physical_time is None:
            continue
        for protocol in events:
            if protocol.get("event") != "lineproto" or protocol.get("state") != "up":
                continue
            protocol_time = _parse_iso_datetime(protocol.get("timestamp"))
            if protocol_time is None or protocol_time < physical_time:
                continue
            delay_seconds = int((protocol_time - physical_time).total_seconds())
            if delay_seconds <= 10:
                return {
                    "physical_link_at": physical.get("timestamp"),
                    "line_protocol_at": protocol.get("timestamp"),
                    "delay_seconds": delay_seconds,
                    "summary": f"Physical link Up -> Line Protocol Up after {delay_seconds} second(s).",
                }
    return None


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _event_timestamp(match: re.Match[str]) -> str:
    value = " ".join(
        (match.group("month"), match.group("day"), match.group("year"), match.group("time"))
    )
    parsed = datetime.strptime(value, "%b %d %Y %H:%M:%S")
    zone = timezone(timedelta(hours=9), name="KST") if match.group("zone") == "KST" else timezone.utc
    return parsed.replace(tzinfo=zone).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
