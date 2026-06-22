from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from ..audit import read_audit_events
from ..collector import CollectorRegistry
from ..diagnostics import assess_device_risks, summarize_findings
from ..models import Device
from ..neighbors import BackboneNeighbor, load_backbone_neighbors
from ..observations import read_latest_observation
from ..parsers import short_interface_name
from .collection import public_device


def build_topology(
    *,
    devices: Iterable[Device],
    data_dir: str | Path,
    backbone_neighbors_path: str | Path,
    audit_log_path: str | Path,
    collector_registry: CollectorRegistry,
) -> dict[str, Any]:
    device_list = list(devices)
    audit_events = read_audit_events(audit_log_path, limit=500)
    indexes = _device_indexes(device_list)
    observations = {
        device.device_id: read_latest_observation(data_dir, device.device_id)
        for device in device_list
    }
    nodes = [
        _node_payload(
            device=device,
            observation=observations.get(device.device_id),
            collector_registry=collector_registry,
            audit_events=audit_events,
        )
        for device in device_list
    ]
    edges = _merge_edges(
        [
            *_reference_edges(load_backbone_neighbors(backbone_neighbors_path), indexes),
            *_live_edges(device_list, observations, indexes),
        ]
    )
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": _summary(nodes, edges),
        "source_note": "Nodes come from inventory. Edges come from live LLDP/CDP snapshots when available, otherwise reference data.",
    }


def _node_payload(
    *,
    device: Device,
    observation: dict[str, Any] | None,
    collector_registry: CollectorRegistry,
    audit_events: list[dict[str, Any]],
) -> dict[str, Any]:
    findings = assess_device_risks(device, audit_events=audit_events)
    severity = _highest_severity(finding.severity for finding in findings)
    stale = observation is None
    status = "stale" if stale and severity == "info" else severity
    return {
        **public_device(device, collector_registry),
        "id": device.device_id,
        "label": device.hostname,
        "status": status,
        "severity": severity,
        "stale": stale,
        "last_seen": observation.get("timestamp") if observation else None,
        "latest_purpose": observation.get("purpose") if observation else None,
        "summary": observation.get("summary", {}) if observation else {},
        "diagnostic_summary": summarize_findings(findings),
        "findings": [asdict(finding) for finding in findings],
        "finding_count": len([finding for finding in findings if finding.severity in {"warning", "critical"}]),
    }


def _reference_edges(neighbors: list[BackboneNeighbor], indexes: dict[str, dict[str, Device]]) -> list[dict[str, Any]]:
    edges = []
    for neighbor in neighbors:
        target = _match_device(indexes, ip=neighbor.management_ip, hostname=neighbor.neighbor_name)
        edges.append(
            {
                "source_device_id": neighbor.source_device_id,
                "target_device_id": target.device_id if target else None,
                "target_label": target.hostname if target else neighbor.neighbor_name,
                "target_management_ip": neighbor.management_ip,
                "local_interface": short_interface_name(neighbor.local_interface),
                "remote_interface": short_interface_name(neighbor.remote_interface),
                "discovery": neighbor.discovery,
                "source_type": "reference",
                "status": _edge_status(neighbor.status, target),
                "notes": neighbor.notes,
                "members": [
                    {
                        "local_interface": short_interface_name(neighbor.local_interface),
                        "remote_interface": short_interface_name(neighbor.remote_interface),
                        "status": neighbor.status,
                        "source_type": "reference",
                    }
                ],
            }
        )
    return edges


def _live_edges(
    devices: list[Device],
    observations: dict[str, dict[str, Any] | None],
    indexes: dict[str, dict[str, Device]],
) -> list[dict[str, Any]]:
    edges = []
    for device in devices:
        observation = observations.get(device.device_id)
        for port in observation.get("ports", []) if observation else []:
            if not isinstance(port, dict):
                continue
            local_interface = short_interface_name(str(port.get("interface") or ""))
            if not _looks_like_interface(local_interface):
                continue
            neighbor_name = str(port.get("neighbor_name") or "").strip()
            neighbor_ip = str(port.get("neighbor_ip") or "").strip() or None
            if not neighbor_name and not neighbor_ip:
                continue
            target = _match_device(indexes, ip=neighbor_ip, hostname=neighbor_name)
            edges.append(
                {
                    "source_device_id": device.device_id,
                    "target_device_id": target.device_id if target else None,
                    "target_label": target.hostname if target else neighbor_name or neighbor_ip,
                    "target_management_ip": target.management_ip if target else neighbor_ip,
                    "local_interface": local_interface,
                    "remote_interface": "",
                    "discovery": "LLDP/CDP",
                    "source_type": "live",
                    "status": "live-managed" if target else "live-unmanaged",
                    "notes": "Live neighbor from latest parsed observation.",
                    "members": [
                        {
                            "local_interface": local_interface,
                            "remote_interface": "",
                            "status": str(port.get("status") or ""),
                            "source_type": "live",
                        }
                    ],
                }
            )
    return edges


def _merge_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        target_key = edge.get("target_device_id") or edge.get("target_label") or ""
        key = (str(edge.get("source_device_id")), str(target_key), str(edge.get("source_type")))
        if key not in grouped:
            grouped[key] = {**edge, "members": list(edge.get("members") or [])}
            continue
        grouped_edge = grouped[key]
        grouped_edge["members"].extend(edge.get("members") or [])
        grouped_edge["local_interface"] = _join_interfaces(member.get("local_interface") for member in grouped_edge["members"])
        grouped_edge["remote_interface"] = _join_interfaces(member.get("remote_interface") for member in grouped_edge["members"])
        if edge.get("status", "").startswith("live"):
            grouped_edge["status"] = edge["status"]
    merged = []
    for index, edge in enumerate(grouped.values(), start=1):
        members = edge.get("members") or []
        edge["id"] = f"edge-{index}"
        edge["link_type"] = "port-channel" if len(members) > 1 or _mentions_port_channel(edge) else "link"
        merged.append(edge)
    return sorted(
        merged,
        key=lambda item: (
            str(item.get("source_device_id") or ""),
            str(item.get("target_device_id") or item.get("target_label") or ""),
            str(item.get("source_type") or ""),
        ),
    )


def _device_indexes(devices: list[Device]) -> dict[str, dict[str, Device]]:
    return {
        "by_ip": {device.management_ip.strip().lower(): device for device in devices if device.management_ip},
        "by_hostname": {device.hostname.strip().lower(): device for device in devices if device.hostname},
        "by_id": {device.device_id.strip().lower(): device for device in devices if device.device_id},
    }


def _match_device(indexes: dict[str, dict[str, Device]], *, ip: str | None, hostname: str | None) -> Device | None:
    if ip and ip.strip().lower() in indexes["by_ip"]:
        return indexes["by_ip"][ip.strip().lower()]
    normalized_hostname = (hostname or "").strip().lower()
    if normalized_hostname in indexes["by_hostname"]:
        return indexes["by_hostname"][normalized_hostname]
    if normalized_hostname in indexes["by_id"]:
        return indexes["by_id"][normalized_hostname]
    return None


def _edge_status(reference_status: str, target: Device | None) -> str:
    if target:
        return "reference-managed"
    if reference_status == "confirmed":
        return "reference-unmanaged"
    return reference_status or "reference"


def _highest_severity(severities: Iterable[str]) -> str:
    rank = {"info": 1, "warning": 2, "critical": 3}
    highest = "info"
    for severity in severities:
        if rank.get(severity, 0) > rank[highest]:
            highest = severity
    return highest


def _summary(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "devices": len(nodes),
        "edges": len(edges),
        "critical": len([node for node in nodes if node["severity"] == "critical"]),
        "warning": len([node for node in nodes if node["severity"] == "warning"]),
        "stale": len([node for node in nodes if node["stale"]]),
        "live_edges": len([edge for edge in edges if edge["source_type"] == "live"]),
        "reference_edges": len([edge for edge in edges if edge["source_type"] == "reference"]),
    }


def _join_interfaces(values: Iterable[Any]) -> str:
    interfaces = []
    for value in values:
        interface = str(value or "").strip()
        if interface and interface not in interfaces:
            interfaces.append(interface)
    return ", ".join(interfaces)


def _mentions_port_channel(edge: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(edge.get("local_interface") or ""),
            str(edge.get("remote_interface") or ""),
            str(edge.get("notes") or ""),
        ]
    ).lower()
    return "port-channel" in text or "lacp" in text


def _looks_like_interface(value: str) -> bool:
    return bool(
        re.match(
            r"^(Et|Ethernet|Gi|GigabitEthernet|Te|TenGigabitEthernet|Fa|FastEthernet|Po|Port-channel|Port-Channel|Vl|Vlan|Ma)\S*$",
            str(value or ""),
            re.I,
        )
    )
