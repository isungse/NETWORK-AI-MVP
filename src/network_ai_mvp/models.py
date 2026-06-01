from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Vendor = Literal["arista", "cisco"]


@dataclass(frozen=True)
class Device:
    device_id: str
    hostname: str
    management_ip: str
    vendor: Vendor
    platform: str
    role: str
    access_method: str
    credential_ref: str
    notes: str = ""


@dataclass(frozen=True)
class CommandPlan:
    device: Device
    purpose: str
    commands: tuple[str, ...]
    read_only: bool = True


@dataclass(frozen=True)
class InterfaceObservation:
    device_id: str
    interface: str
    status: str
    vlan: str | None
    speed_mbps: int | None
    duplex: str | None
    description: str = ""
    is_uplink: bool = False


@dataclass(frozen=True)
class InterfaceCounters:
    device_id: str
    interface: str
    input_errors: int = 0
    crc_errors: int = 0
    runts: int = 0
    output_discards: int = 0
    link_status_changes: int = 0


@dataclass(frozen=True)
class PortObservation:
    device_id: str
    interface: str
    status: str | None = None
    vlan: str | None = None
    duplex: str | None = None
    speed: str | None = None
    speed_mbps: int | None = None
    description: str = ""
    endpoint_ips: tuple[str, ...] = ()
    endpoint_macs: tuple[str, ...] = ()
    neighbor_name: str | None = None
    neighbor_ip: str | None = None
    neighbor_platform: str | None = None
    fcs_errors: int = 0
    align_errors: int = 0
    symbol_errors: int = 0
    rx_errors: int = 0
    runts: int = 0
    giants: int = 0
    tx_errors: int = 0
    source_timestamp: str = ""
    source_purpose: str = ""
    source: str = "latest_collection"


@dataclass(frozen=True)
class DiagnosticFinding:
    severity: Literal["info", "warning", "critical"]
    device_id: str
    interface: str | None
    title: str
    evidence: str
    next_step: str
