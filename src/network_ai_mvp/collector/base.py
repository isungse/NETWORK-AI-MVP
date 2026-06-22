from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from ..models import CommandPlan, Device


class ExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    device_id: str
    hostname: str
    management_ip: str
    purpose: str
    commands: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int


class CollectorAdapter(Protocol):
    def supports(self, device: Device) -> bool:
        """Return whether this adapter can collect from the supplied device."""

    def collect(
        self,
        device: Device,
        plans: Sequence[CommandPlan],
        *,
        credential_path: str | Path,
    ) -> tuple[CommandResult, ...]:
        """Collect all supplied plans for one device."""


class CollectorRegistry:
    def __init__(self, adapters: Sequence[CollectorAdapter]) -> None:
        self._adapters = tuple(adapters)

    def adapter_for(self, device: Device) -> CollectorAdapter:
        for adapter in self._adapters:
            if adapter.supports(device):
                return adapter
        raise ExecutionError(
            f"Device {device.device_id} access_method is {device.access_method}; "
            "no read-only collector adapter supports this device."
        )

    def supports(self, device: Device) -> bool:
        return any(adapter.supports(device) for adapter in self._adapters)
