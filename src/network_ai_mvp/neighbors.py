from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BackboneNeighbor:
    source_device_id: str
    local_interface: str
    neighbor_name: str
    management_ip: str | None
    vendor: str
    platform: str
    remote_interface: str
    discovery: str
    status: str
    notes: str = ""


def load_backbone_neighbors(path: str | Path) -> list[BackboneNeighbor]:
    reference_path = Path(path)
    if not reference_path.exists():
        return []

    with reference_path.open(encoding="utf-8") as file_obj:
        raw_neighbors = json.load(file_obj)

    if not isinstance(raw_neighbors, list):
        raise ValueError("Backbone neighbor reference must be a JSON list")

    return [_neighbor_from_row(row, index) for index, row in enumerate(raw_neighbors, start=1)]


def get_neighbors_for_device(path: str | Path, device_id: str) -> list[BackboneNeighbor]:
    return [
        neighbor
        for neighbor in load_backbone_neighbors(path)
        if neighbor.source_device_id == device_id
    ]


def _neighbor_from_row(row: object, index: int) -> BackboneNeighbor:
    if not isinstance(row, dict):
        raise ValueError(f"Backbone neighbor entry {index} must be an object")

    required = {
        "source_device_id",
        "local_interface",
        "neighbor_name",
        "vendor",
        "platform",
        "remote_interface",
        "discovery",
        "status",
    }
    missing = required - set(row)
    if missing:
        raise ValueError(f"Backbone neighbor entry {index} is missing: {sorted(missing)}")

    management_ip = row.get("management_ip")
    if management_ip is not None and not isinstance(management_ip, str):
        raise ValueError(f"Backbone neighbor entry {index} management_ip must be null or string")

    return BackboneNeighbor(
        source_device_id=str(row["source_device_id"]).strip(),
        local_interface=str(row["local_interface"]).strip(),
        neighbor_name=str(row["neighbor_name"]).strip(),
        management_ip=management_ip.strip() if isinstance(management_ip, str) else None,
        vendor=str(row["vendor"]).strip().lower(),
        platform=str(row["platform"]).strip(),
        remote_interface=str(row["remote_interface"]).strip(),
        discovery=str(row["discovery"]).strip(),
        status=str(row["status"]).strip(),
        notes=str(row.get("notes", "")).strip(),
    )
