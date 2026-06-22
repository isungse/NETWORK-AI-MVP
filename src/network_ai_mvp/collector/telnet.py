from __future__ import annotations

import subprocess
from base64 import b64encode
from pathlib import Path
from typing import Sequence

from ..models import CommandPlan, Device
from ..policy import validate_commands
from .base import CommandResult, ExecutionError

DEFAULT_TELNET_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "backbone_telnet_readonly.ps1"


class TelnetCollector:
    """Collect validated read-only command plans through the existing PowerShell Telnet helper."""

    def __init__(
        self,
        *,
        script_path: str | Path = DEFAULT_TELNET_SCRIPT,
        powershell_executable: str = "powershell",
        timeout_seconds: int = 120,
    ) -> None:
        self.script_path = Path(script_path)
        self.powershell_executable = powershell_executable
        self.timeout_seconds = timeout_seconds

    def supports(self, device: Device) -> bool:
        return device.access_method == "telnet"

    def collect(
        self,
        device: Device,
        plans: Sequence[CommandPlan],
        *,
        credential_path: str | Path,
    ) -> tuple[CommandResult, ...]:
        if not self.supports(device):
            raise ExecutionError(
                f"Device {device.device_id} access_method is {device.access_method}; "
                "this collector only supports explicit Telnet MVP devices."
            )
        if not plans:
            return ()
        for plan in plans:
            if plan.device != device:
                raise ExecutionError("All command plans in one collection must target the same device.")
        combined = CommandPlan(
            device=device,
            purpose=plans[0].purpose if len(plans) == 1 else "check",
            commands=_unique_commands(plans),
        )
        return (self.run(combined, credential_path=credential_path),)

    def run(self, plan: CommandPlan, *, credential_path: str | Path) -> CommandResult:
        if not self.supports(plan.device):
            raise ExecutionError(
                f"Device {plan.device.device_id} access_method is {plan.device.access_method}; "
                "this collector only supports explicit Telnet MVP devices."
            )
        if not self.script_path.exists():
            raise ExecutionError(f"Read-only Telnet helper script not found: {self.script_path}")

        validate_commands(plan.device.vendor, plan.commands)
        args = self.build_args(plan, credential_path=credential_path)
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExecutionError(
                f"Read-only Telnet command timed out after {self.timeout_seconds} seconds "
                f"for device {plan.device.device_id}."
            ) from exc
        return CommandResult(
            device_id=plan.device.device_id,
            hostname=plan.device.hostname,
            management_ip=plan.device.management_ip,
            purpose=plan.purpose,
            commands=plan.commands,
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    def build_args(self, plan: CommandPlan, *, credential_path: str | Path) -> list[str]:
        validate_commands(plan.device.vendor, plan.commands)
        command = (
            f"& {_ps_quote(str(self.script_path))} "
            f"-HostName {_ps_quote(plan.device.management_ip)} "
            f"-CredentialPath {_ps_quote(str(credential_path))} "
            f"-Commands @({_ps_array(plan.commands)})"
        )
        encoded_command = b64encode(command.encode("utf-16le")).decode("ascii")
        return [
            self.powershell_executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded_command,
        ]


def _ps_array(values: tuple[str, ...]) -> str:
    return ",".join(_ps_quote(value) for value in values)


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _unique_commands(plans: Sequence[CommandPlan]) -> tuple[str, ...]:
    commands: list[str] = []
    seen: set[str] = set()
    for plan in plans:
        for command in plan.commands:
            if command not in seen:
                seen.add(command)
                commands.append(command)
    return tuple(commands)
