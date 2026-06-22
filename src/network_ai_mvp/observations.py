from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .audit import redact_text
from .executor import CommandResult
from .models import Device
from .parsers import parse_collection_ports, short_interface_name
from .thresholds import has_high_error_counters, is_low_speed_connected_port

LOGGER = logging.getLogger(__name__)


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
    run_id = f"{safe_timestamp}_{safe_purpose}"

    raw_stdout = redact_text(result.stdout)
    raw_stderr = redact_text(result.stderr)
    raw_record = {
        "run_id": run_id,
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

    raw_path = root / "raw" / safe_device_id / f"{run_id}.json"
    _write_json(raw_path, raw_record)

    ports = parse_collection_ports(
        device=device,
        purpose=result.purpose,
        commands=tuple(result.commands),
        stdout=raw_stdout,
        timestamp=timestamp,
    )
    parsed_record = {
        "run_id": run_id,
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
    observation_dir = root / "observations" / safe_device_id
    latest_path = observation_dir / "latest.json"
    history_path = observation_dir / f"{run_id}.json"
    _write_json(latest_path, parsed_record)
    _write_json(history_path, parsed_record)
    _update_observation_index(
        observation_dir / "index.json",
        {
            "run_id": run_id,
            "timestamp": timestamp,
            "purpose": result.purpose,
            "history_path": str(history_path.relative_to(root)),
            "raw_path": str(raw_path.relative_to(root)),
            "success": result.returncode == 0,
            "summary": parsed_record["summary"],
        },
    )
    return parsed_record


def read_latest_observation(base_dir: str | Path, device_id: str) -> dict[str, Any] | None:
    root = _safe_root(base_dir)
    path = root / "observations" / _safe_name(device_id) / "latest.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        LOGGER.warning("Ignoring unreadable latest observation %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def read_observation_index(base_dir: str | Path, device_id: str) -> list[dict[str, Any]]:
    root = _safe_root(base_dir)
    path = root / "observations" / _safe_name(device_id) / "index.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        LOGGER.warning("Ignoring unreadable observation index %s: %s", path, exc)
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


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
        if is_low_speed_connected_port(port):
            low_speed += 1
        if port.get("status") in {"disabled", "errdisabled"}:
            disabled += 1
        if has_high_error_counters(port):
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

def _update_observation_index(path: Path, record: dict[str, Any]) -> None:
    records = []
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                records = [item for item in payload if isinstance(item, dict)]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            LOGGER.warning("Rebuilding unreadable observation index %s: %s", path, exc)

    records = [item for item in records if item.get("run_id") != record["run_id"]]
    records.insert(0, record)
    records.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    _write_json(path, records)


def _write_json(path: Path, payload: Any) -> None:
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
