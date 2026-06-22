from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

LOW_SPEED_CONNECTED_THRESHOLD_MBPS = 1000
HIGH_ERROR_COUNTER_THRESHOLD = 1000
HIGH_ERROR_COUNTER_FIELDS = ("fcs_errors", "rx_errors", "runts", "tx_errors")


def is_low_speed_connected_port(port: object) -> bool:
    row = _port_mapping(port)
    if not row:
        return False
    return (
        str(row.get("status") or "").lower() == "connected"
        and isinstance(row.get("speed_mbps"), int)
        and int(row["speed_mbps"]) < LOW_SPEED_CONNECTED_THRESHOLD_MBPS
    )


def high_error_counter_value(port: object) -> int:
    row = _port_mapping(port)
    if not row:
        return 0
    return max((_int(row.get(field)) for field in HIGH_ERROR_COUNTER_FIELDS), default=0)


def has_high_error_counters(port: object) -> bool:
    return high_error_counter_value(port) >= HIGH_ERROR_COUNTER_THRESHOLD


def _port_mapping(port: object) -> Mapping[str, Any] | None:
    if isinstance(port, Mapping):
        return port
    if is_dataclass(port) and not isinstance(port, type):
        return asdict(port)
    return None


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
