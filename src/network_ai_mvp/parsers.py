from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict

from .models import Device, PortObservation


def parse_collection_ports(
    *,
    device: Device,
    purpose: str,
    commands: tuple[str, ...],
    stdout: str,
    timestamp: str,
) -> list[dict[str, object]]:
    sections = command_sections(stdout)
    status_rows = parse_interface_status(sections.get("show interfaces status", ""))
    descriptions = parse_interface_descriptions(sections.get("show interfaces description", ""))
    counters = parse_interface_error_counters(sections.get("show interfaces counters errors", ""))
    mac_entries = parse_mac_address_table(sections.get("show mac address-table", ""))
    arp_entries = parse_ip_arp(sections.get("show ip arp", ""))
    lldp_neighbors = parse_lldp_neighbors(sections.get("show lldp neighbors", ""))

    ports = set(status_rows) | set(descriptions) | set(counters) | set(mac_entries) | set(lldp_neighbors)
    if not ports and not commands:
        return []

    ips_by_mac = defaultdict(set)
    for entry in arp_entries:
        ips_by_mac[entry["mac"]].add(entry["ip"])

    endpoint_macs_by_port = defaultdict(set)
    endpoint_ips_by_port = defaultdict(set)
    for port, macs in mac_entries.items():
        for mac in macs:
            endpoint_macs_by_port[port].add(mac)
            endpoint_ips_by_port[port].update(ips_by_mac.get(normalize_mac(mac), set()))
            endpoint_ips_by_port[port].update(ips_by_mac.get(mac, set()))

    observations = []
    for port in sorted(ports, key=interface_sort_key):
        status = status_rows.get(port, {})
        counter = counters.get(port, {})
        neighbor = lldp_neighbors.get(port, {})
        observation = PortObservation(
            device_id=device.device_id,
            interface=port,
            status=status.get("status"),
            vlan=status.get("vlan"),
            duplex=status.get("duplex"),
            speed=status.get("speed"),
            speed_mbps=speed_mbps(status.get("speed")),
            description=descriptions.get(port, ""),
            endpoint_ips=tuple(sorted(endpoint_ips_by_port.get(port, set()), key=ip_sort_key)),
            endpoint_macs=tuple(sorted(endpoint_macs_by_port.get(port, set()))),
            neighbor_name=neighbor.get("neighbor_name"),
            neighbor_ip=neighbor.get("neighbor_ip"),
            neighbor_platform=neighbor.get("neighbor_platform"),
            fcs_errors=int(counter.get("fcs_errors", 0)),
            align_errors=int(counter.get("align_errors", 0)),
            symbol_errors=int(counter.get("symbol_errors", 0)),
            rx_errors=int(counter.get("rx_errors", 0)),
            runts=int(counter.get("runts", 0)),
            giants=int(counter.get("giants", 0)),
            tx_errors=int(counter.get("tx_errors", 0)),
            source_timestamp=timestamp,
            source_purpose=purpose,
        )
        observations.append(asdict(observation))
    return observations


def command_sections(stdout: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in str(stdout or "").splitlines():
        match = re.match(r"^===== (.+?) =====$", line)
        if match:
            current = match.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}


def parse_interface_status(section: str) -> dict[str, dict[str, str]]:
    status_tokens = {"connected", "notconnect", "disabled", "errdisabled"}
    rows: dict[str, dict[str, str]] = {}
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Port ") or _is_prompt(line):
            continue
        parts = line.split()
        status_index = next(
            (index for index, part in enumerate(parts[1:], start=1) if part.lower() in status_tokens),
            -1,
        )
        if status_index < 1 or len(parts) < status_index + 4:
            continue
        port = short_interface_name(parts[0])
        rows[port] = {
            "name": " ".join(parts[1:status_index]),
            "status": parts[status_index].lower(),
            "vlan": parts[status_index + 1],
            "duplex": parts[status_index + 2],
            "speed": parts[status_index + 3],
        }
    return rows


def parse_interface_descriptions(section: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for raw_line in section.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if (
            not stripped
            or stripped.lower() == "show interfaces description"
            or line.lstrip().startswith("Interface ")
            or _is_prompt(stripped)
        ):
            continue
        parts = stripped.split()
        if len(parts) < 3:
            continue
        description_start = 4 if len(parts) >= 4 and parts[1].lower() == "admin" and parts[2].lower() == "down" else 3
        rows[short_interface_name(parts[0])] = " ".join(parts[description_start:])
    return rows


def parse_interface_error_counters(section: str) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("Port ") or _is_prompt(line):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        rows[short_interface_name(parts[0])] = {
            "fcs_errors": _int(parts[1]),
            "align_errors": _int(parts[2]),
            "symbol_errors": _int(parts[3]),
            "rx_errors": _int(parts[4]),
            "runts": _int(parts[5]),
            "giants": _int(parts[6]),
            "tx_errors": _int(parts[7]),
        }
    return rows


def parse_mac_address_table(section: str) -> dict[str, set[str]]:
    rows: dict[str, set[str]] = defaultdict(set)
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line or _is_prompt(line):
            continue
        mac_match = re.search(r"\b([0-9a-f]{4}[.:-][0-9a-f]{4}[.:-][0-9a-f]{4})\b", line, re.I)
        if not mac_match:
            continue
        parts = line.split()
        mac_index = next((index for index, part in enumerate(parts) if canonical_mac(part) == canonical_mac(mac_match.group(1))), -1)
        if mac_index < 0:
            continue
        port = next((part for part in parts[mac_index + 1 :] if _looks_like_interface(part)), "")
        if not port or port.upper() == "CPU":
            continue
        rows[short_interface_name(port)].add(canonical_mac(mac_match.group(1)))
    return dict(rows)


def parse_ip_arp(section: str) -> list[dict[str, str]]:
    rows = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line or _is_prompt(line):
            continue
        match = re.search(
            r"\b(\d{1,3}(?:\.\d{1,3}){3})\b\s+\S+\s+([0-9a-f]{4}[.:-][0-9a-f]{4}[.:-][0-9a-f]{4})\b",
            line,
            re.I,
        )
        if match:
            rows.append({"ip": match.group(1), "mac": canonical_mac(match.group(2))})
    return rows


def parse_lldp_neighbors(section: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.lower() in {"show lldp neighbors", "show lldp neighbors detail"}
            or line.startswith(("Last table change", "Number of"))
            or "Neighbor Device ID" in line
            or _is_prompt(line)
        ):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        local_port = short_interface_name(parts[0])
        rows[local_port] = {"neighbor_name": parts[1], "neighbor_platform": "", "neighbor_ip": ""}
    return rows


def short_interface_name(value: str) -> str:
    return (
        str(value or "")
        .replace("TenGigabitEthernet", "Te")
        .replace("GigabitEthernet", "Gi")
        .replace("FastEthernet", "Fa")
        .replace("Ethernet", "Et")
        .replace("Port-channel", "Po")
        .replace("Port-Channel", "Po")
        .replace("Vlan", "Vl")
    )


def canonical_mac(value: str) -> str:
    normalized = normalize_mac(value)
    if len(normalized) != 12:
        return str(value or "")
    return f"{normalized[:4]}.{normalized[4:8]}.{normalized[8:]}"


def normalize_mac(value: str) -> str:
    return re.sub(r"[^0-9a-f]", "", str(value or "").lower())


def speed_mbps(value: str | None) -> int | None:
    normalized = str(value or "").lower().replace("a-", "")
    match = re.match(r"^(\d+)(m|g)$", normalized)
    if not match:
        return None
    amount = int(match.group(1))
    return amount * 1000 if match.group(2) == "g" else amount


def interface_sort_key(value: str) -> tuple[str, int, str]:
    match = re.match(r"([A-Za-z-]+)(\d+)", value)
    if not match:
        return (value, 0, value)
    return (match.group(1), int(match.group(2)), value)


def ip_sort_key(value: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in str(value or "0.0.0.0").split(".") if part.isdigit()]
    return tuple((parts + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def _int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def _is_prompt(line: str) -> bool:
    return line.endswith(">") or line.endswith("#")


def _looks_like_interface(value: str) -> bool:
    return bool(
        re.match(
            r"^(Et|Ethernet|Gi|GigabitEthernet|Te|TenGigabitEthernet|Fa|FastEthernet|Po|Port-channel|Port-Channel|Vl|Vlan|Ma)\S*$",
            str(value or ""),
            re.I,
        )
    ) or str(value or "").lower() == "switch"
