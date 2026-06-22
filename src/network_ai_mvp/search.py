from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .inventory import load_devices
from .neighbors import get_neighbors_for_device
from .observations import latest_ports
from .parsers import canonical_mac, normalize_mac, short_interface_name


def search_network_state(
    *,
    query: str,
    inventory_path: str | Path,
    observations_dir: str | Path,
    backbone_neighbors_path: str | Path,
) -> list[dict[str, Any]]:
    normalized = _normalize(query)
    if not normalized:
        return []

    devices = load_devices(inventory_path)
    results: list[dict[str, Any]] = []

    for device in devices:
        haystack = " ".join(
            [
                device.device_id,
                device.hostname,
                device.management_ip,
                device.vendor,
                device.platform,
                device.role,
                device.notes,
            ]
        )
        if _matches(normalized, haystack):
            results.append(
                {
                    "type": "device",
                    "source": "inventory",
                    "device_id": device.device_id,
                    "hostname": device.hostname,
                    "management_ip": device.management_ip,
                    "label": f"{device.device_id} ({device.management_ip})",
                    "summary": f"{device.vendor} {device.platform} {device.role}",
                }
            )

        for port in latest_ports(observations_dir, device.device_id):
            if _port_matches(normalized, port):
                results.append(
                    {
                        "type": "port",
                        "source": "latest_observation",
                        "device_id": device.device_id,
                        "hostname": device.hostname,
                        "management_ip": device.management_ip,
                        "interface": port.get("interface"),
                        "label": f"{device.device_id} {port.get('interface')}",
                        "summary": _port_summary(port),
                    }
                )

    for device in devices:
        for neighbor in get_neighbors_for_device(backbone_neighbors_path, device.device_id):
            neighbor_data = asdict(neighbor)
            if _matches(normalized, " ".join(str(value or "") for value in neighbor_data.values())):
                results.append(
                    {
                        "type": "neighbor",
                        "source": "reference_neighbor",
                        "device_id": device.device_id,
                        "interface": short_interface_name(neighbor.local_interface),
                        "label": f"{device.device_id} {short_interface_name(neighbor.local_interface)} -> {neighbor.neighbor_name}",
                        "summary": (
                            "Reference only. Re-check live CDP/LLDP before acting. "
                            f"ip={neighbor.management_ip or '-'} platform={neighbor.platform or '-'}"
                        ),
                    }
                )

    return results[:50]


def _port_matches(normalized: str, port: dict[str, Any]) -> bool:
    values = [
        str(port.get("interface") or ""),
        str(port.get("description") or ""),
        str(port.get("status") or ""),
        str(port.get("vlan") or ""),
        str(port.get("speed") or ""),
        str(port.get("neighbor_name") or ""),
        str(port.get("neighbor_ip") or ""),
        str(port.get("neighbor_platform") or ""),
        " ".join(str(value) for value in port.get("endpoint_ips") or []),
        " ".join(str(value) for value in port.get("endpoint_macs") or []),
    ]
    return _matches(normalized, " ".join(values))


def _matches(normalized_query: str, value: str) -> bool:
    normalized_value = _normalize(value)
    if normalized_query in normalized_value:
        return True
    if _looks_like_mac(normalized_query):
        return normalize_mac(normalized_query) in normalize_mac(normalized_value)
    return short_interface_name(normalized_query).lower() in short_interface_name(normalized_value).lower()


def _normalize(value: str) -> str:
    return str(value or "").strip().lower()


def _looks_like_mac(value: str) -> bool:
    return len(normalize_mac(value)) >= 6


def _port_summary(port: dict[str, Any]) -> str:
    endpoint_ips = ",".join(port.get("endpoint_ips") or [])
    endpoint_macs = ",".join(canonical_mac(mac) for mac in (port.get("endpoint_macs") or []))
    return (
        f"status={port.get('status') or '-'} vlan={port.get('vlan') or '-'} "
        f"speed={port.get('speed') or '-'} neighbor={port.get('neighbor_name') or '-'} "
        f"ips={endpoint_ips or '-'} macs={endpoint_macs or '-'}"
    )
