from __future__ import annotations

import subprocess
from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path

from .models import CommandPlan
from .policy import validate_commands

DEFAULT_TELNET_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backbone_telnet_readonly.ps1"


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


class PowerShellTelnetReadOnlyExecutor:
    """Execute validated read-only command plans through the existing PowerShell Telnet helper."""

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

    def run(self, plan: CommandPlan, *, credential_path: str | Path) -> CommandResult:
        if plan.device.access_method != "telnet":
            raise ExecutionError(
                f"Device {plan.device.device_id} access_method is {plan.device.access_method}; "
                "this executor only supports explicit Telnet MVP devices."
            )
        if not self.script_path.exists():
            raise ExecutionError(f"Read-only Telnet helper script not found: {self.script_path}")

        validate_commands(plan.device.vendor, plan.commands)
        args = self.build_args(plan, credential_path=credential_path)
        completed = subprocess.run(
            args,
            capture_output=True,
            check=False,
            text=True,
            timeout=self.timeout_seconds,
        )
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
