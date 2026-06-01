from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .audit import redact_text
from .executor import CommandResult
from .models import Device
from .parsers import parse_collection_ports, short_interface_name


class ObservationStoreError(RuntimeError):
    pass


def current_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def store_collection_observation(
    base_dir: str | Path,
    *,
    device: Device,
    result: CommandResult,
    timestamp: str | None = None,
) -> dict[str, Any]:
    timestamp = timestamp or current_timestamp()
    root = _safe_root(base_dir)
    safe_device_id = _safe_name(device.device_id)
    safe_timestamp = _safe_name(timestamp)
    safe_purpose = _safe_name(result.purpose)

    raw_stdout = redact_text(result.stdout)
    raw_stderr = redact_text(result.stderr)
    raw_record = {
        "timestamp": timestamp,
        "device_id": device.device_id,
        "hostname": device.hostname,
        "management_ip": device.management_ip,
        "purpose": result.purpose,
        "commands": list(result.commands),
        "stdout": raw_stdout,
        "stderr": raw_stderr,
        "returncode": result.returncode,
        "success": result.returncode == 0,
    }

    raw_path = root / "raw" / safe_device_id / f"{safe_timestamp}_{safe_purpose}.json"
    _write_json(raw_path, raw_record)

    ports = parse_collection_ports(
        device=device,
        purpose=result.purpose,
        commands=tuple(result.commands),
        stdout=raw_stdout,
        timestamp=timestamp,
    )
    parsed_record = {
        "timestamp": timestamp,
        "device": {
            "device_id": device.device_id,
            "hostname": device.hostname,
            "management_ip": device.management_ip,
            "vendor": device.vendor,
            "platform": device.platform,
            "role": device.role,
            "access_method": device.access_method,
            "notes": device.notes,
        },
        "purpose": result.purpose,
        "commands": list(result.commands),
        "raw_path": str(raw_path.relative_to(root)),
        "ports": ports,
        "summary": summarize_ports(ports),
    }
    latest_path = root / "observations" / safe_device_id / "latest.json"
    history_path = root / "observations" / safe_device_id / f"{safe_timestamp}_{safe_purpose}.json"
    _write_json(latest_path, parsed_record)
    _write_json(history_path, parsed_record)
    return parsed_record


def read_latest_observation(base_dir: str | Path, device_id: str) -> dict[str, Any] | None:
    root = _safe_root(base_dir)
    path = root / "observations" / _safe_name(device_id) / "latest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def latest_ports(base_dir: str | Path, device_id: str) -> list[dict[str, Any]]:
    observation = read_latest_observation(base_dir, device_id)
    if not observation:
        return []
    return list(observation.get("ports") or [])


def find_latest_port(base_dir: str | Path, device_id: str, interface: str) -> dict[str, Any] | None:
    target = short_interface_name(interface).lower()
    for port in latest_ports(base_dir, device_id):
        if str(port.get("interface", "")).lower() == target:
            return port
    return None


def summarize_ports(ports: list[dict[str, Any]]) -> dict[str, int]:
    low_speed = 0
    disabled = 0
    high_errors = 0
    endpoints = 0
    for port in ports:
        if port.get("status") == "connected" and _is_low_speed(port.get("speed_mbps")):
            low_speed += 1
        if port.get("status") in {"disabled", "errdisabled"}:
            disabled += 1
        if max(
            int(port.get("fcs_errors") or 0),
            int(port.get("rx_errors") or 0),
            int(port.get("runts") or 0),
            int(port.get("tx_errors") or 0),
        ) >= 1000:
            high_errors += 1
        if port.get("endpoint_ips") or port.get("endpoint_macs"):
            endpoints += 1
    return {
        "total_ports": len(ports),
        "low_speed_connected_ports": low_speed,
        "disabled_ports": disabled,
        "high_error_ports": high_errors,
        "ports_with_endpoints": endpoints,
    }


def _is_low_speed(value: object) -> bool:
    return isinstance(value, int) and value < 1000


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_root(base_dir: str | Path) -> Path:
    root = Path(base_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_name(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)
    if not safe.strip("_"):
        raise ObservationStoreError("Unsafe empty observation path component.")
    return safe
