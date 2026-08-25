from __future__ import annotations

import subprocess
from base64 import b64encode
from pathlib import Path

from .collector.base import CommandResult, ExecutionError
from .models import CommandPlan
from .write_policy import validate_write_commands

DEFAULT_TELNET_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backbone_telnet_readonly.ps1"


class PowerShellTelnetWriteExecutor:
    """Execute only the fixed single-interface admin-state command shape."""

    def __init__(
        self,
        *,
        script_path: str | Path = DEFAULT_TELNET_SCRIPT,
        powershell_executable: str = "powershell",
        timeout_seconds: int = 90,
    ) -> None:
        self.script_path = Path(script_path)
        self.powershell_executable = powershell_executable
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        plan: CommandPlan,
        *,
        credential_path: str | Path,
        enable_credential_path: str | Path | None = None,
    ) -> CommandResult:
        if plan.read_only:
            raise ExecutionError("Write executor requires a non-read-only command plan.")
        validate_write_commands(plan.commands)
        if plan.device.access_method != "telnet":
            raise ExecutionError(f"Unsupported write access method: {plan.device.access_method}")
        if not self.script_path.exists():
            raise ExecutionError(f"Telnet helper script not found: {self.script_path}")

        command = (
            f"& {_ps_quote(str(self.script_path))} "
            f"-HostName {_ps_quote(plan.device.management_ip)} "
            f"-CredentialPath {_ps_quote(str(credential_path))} "
        )
        if enable_credential_path:
            command += f"-EnableCredentialPath {_ps_quote(str(enable_credential_path))} "
        command += f"-Commands @({_ps_array(plan.commands)})"
        encoded_command = b64encode(command.encode("utf-16le")).decode("ascii")

        try:
            completed = subprocess.run(
                [
                    self.powershell_executable,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-EncodedCommand",
                    encoded_command,
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExecutionError(
                f"Controlled interface change timed out after {self.timeout_seconds} seconds."
            ) from exc

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        cli_error = _cli_error(stdout, stderr)
        returncode = completed.returncode or (1 if cli_error else 0)
        if cli_error and not stderr:
            stderr = cli_error
        return CommandResult(
            device_id=plan.device.device_id,
            hostname=plan.device.hostname,
            management_ip=plan.device.management_ip,
            purpose=plan.purpose,
            commands=plan.commands,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )


def _cli_error(stdout: str, stderr: str) -> str:
    combined = f"{stdout}\n{stderr}".lower()
    markers = (
        "% invalid input",
        "% incomplete command",
        "% ambiguous command",
        "authorization failed",
        "access denied",
        "login failed",
        "enable failed",
    )
    return next((marker for marker in markers if marker in combined), "")


def _ps_array(values: tuple[str, ...]) -> str:
    return ",".join(_ps_quote(value) for value in values)


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
