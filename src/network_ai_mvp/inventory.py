from __future__ import annotations

import csv
from pathlib import Path

from .models import Device

REQUIRED_COLUMNS = {
    "device_id",
    "hostname",
    "management_ip",
    "vendor",
    "platform",
    "role",
    "access_method",
    "credential_ref",
}


class InventoryError(ValueError):
    pass


def load_devices(path: str | Path) -> list[Device]:
    inventory_path = Path(path)
    with inventory_path.open(newline="", encoding="utf-8") as file_obj:
        reader = csv.DictReader(file_obj)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise InventoryError(f"Inventory is missing required columns: {sorted(missing)}")

        devices: list[Device] = []
        seen_ids: set[str] = set()
        seen_ips: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            device = _device_from_row(row, line_number)
            if device.device_id in seen_ids:
                raise InventoryError(f"Duplicate device_id at line {line_number}: {device.device_id}")
            if device.management_ip in seen_ips:
                raise InventoryError(f"Duplicate management_ip at line {line_number}: {device.management_ip}")
            seen_ids.add(device.device_id)
            seen_ips.add(device.management_ip)
            devices.append(device)
    return devices


def get_device(devices: list[Device], device_id: str) -> Device:
    for device in devices:
        if device.device_id == device_id:
            return device
    raise InventoryError(f"Unknown device_id: {device_id}")


def _device_from_row(row: dict[str, str], line_number: int) -> Device:
    vendor = row["vendor"].strip().lower()
    if vendor not in {"arista", "cisco"}:
        raise InventoryError(f"Unsupported vendor at line {line_number}: {vendor}")

    credential_ref = row["credential_ref"].strip()
    if "\\" in credential_ref or "/" in credential_ref or "." in credential_ref:
        raise InventoryError(
            f"credential_ref must be a logical secret name, not a path or filename, at line {line_number}"
        )

    return Device(
        device_id=row["device_id"].strip(),
        hostname=row["hostname"].strip(),
        management_ip=row["management_ip"].strip(),
        vendor=vendor,  # type: ignore[arg-type]
        platform=row["platform"].strip(),
        role=row["role"].strip(),
        access_method=row["access_method"].strip().lower(),
        credential_ref=credential_ref,
        notes=row.get("notes", "").strip(),
    )
