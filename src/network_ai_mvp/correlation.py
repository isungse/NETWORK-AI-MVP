from __future__ import annotations

import json
from pathlib import Path

from .parsers import (
    command_sections,
    interface_sort_key,
    ip_sort_key,
    parse_interface_descriptions,
    parse_interface_status,
    parse_ip_arp,
    parse_mac_address_table,
)


def build_port_endpoint_trace(stdout: str, data_dir: str | Path) -> list[dict[str, object]]:
    sections = command_sections(stdout)
    status_rows = parse_interface_status(sections.get("show interfaces status", ""))
    descriptions = parse_interface_descriptions(sections.get("show interfaces description", ""))
    macs_by_port = parse_mac_address_table(sections.get("show mac address-table", ""))
    ips_by_mac = ips_by_mac_from_stdout(stdout)
    for mac, ips in latest_observation_ips_by_mac(data_dir).items():
        ips_by_mac.setdefault(mac, set()).update(ips)

    rows: list[dict[str, object]] = []
    for port in sorted(macs_by_port, key=interface_sort_key):
        status = status_rows.get(port, {})
        endpoints = []
        for mac in sorted(macs_by_port[port]):
            endpoints.append(
                {
                    "mac": mac,
                    "ips": tuple(sorted(ips_by_mac.get(mac, set()), key=ip_sort_key)),
                }
            )
        rows.append(
            {
                "interface": port,
                "status": status.get("status") or "",
                "vlan": status.get("vlan") or "",
                "speed": status.get("speed") or "",
                "description": descriptions.get(port, ""),
                "endpoints": endpoints,
            }
        )
    return rows


def latest_observation_ips_by_mac(data_dir: str | Path) -> dict[str, set[str]]:
    raw_root = Path(data_dir) / "raw"
    ips_by_mac: dict[str, set[str]] = {}
    if not raw_root.exists():
        return ips_by_mac

    for device_dir in raw_root.iterdir():
        if not device_dir.is_dir():
            continue
        raw_files = sorted(
            (path for path in device_dir.glob("*.json") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for raw_file in raw_files:
            try:
                payload = json.loads(raw_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            stdout = str(payload.get("stdout") or "")
            if "show ip arp" not in stdout:
                continue
            for mac, ips in ips_by_mac_from_stdout(stdout).items():
                ips_by_mac.setdefault(mac, set()).update(ips)
            break
    return ips_by_mac


def ips_by_mac_from_stdout(stdout: str) -> dict[str, set[str]]:
    sections = command_sections(stdout)
    ips_by_mac: dict[str, set[str]] = {}
    for entry in parse_ip_arp(sections.get("show ip arp", "")):
        ips_by_mac.setdefault(entry["mac"], set()).add(entry["ip"])
    return ips_by_mac
