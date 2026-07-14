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


def build_port_connection_diagnostic(
    base_dir: str | Path,
    *,
    device_id: str,
    interface: str,
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
    link_events = _read_link_events(base_dir, device_id, interface)
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
        "ping_available": bool(endpoint_ips),
    }


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


def _read_link_events(base_dir: str | Path, device_id: str, interface: str) -> list[dict[str, Any]]:
    raw_dir = Path(base_dir).resolve() / "raw" / device_id
    target = short_interface_name(interface).lower()
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not raw_dir.exists():
        return []

    for path in sorted(raw_dir.glob("*.json")):
        payload = _read_json(path)
        if not payload:
            continue
        stdout = str(payload.get("stdout") or "")
        for match in LINK_EVENT_RE.finditer(stdout):
            event_interface = short_interface_name(match.group("interface").strip())
            if event_interface.lower() != target:
                continue
            timestamp = _event_timestamp(match)
            event = {
                "timestamp": timestamp,
                "interface": event_interface,
                "event": match.group("family").lower(),
                "state": match.group("state").lower(),
                "message": match.group(0).strip(),
            }
            unique[(timestamp, event["event"], event["state"])] = event
    return sorted(unique.values(), key=lambda item: item["timestamp"])


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
