"""Bounded Telnet transport for the on-premises Linux runtime.

Credentials are JSON delivered by systemd's encrypted credential facility.
Authentication transcripts are never returned as collection evidence.
"""
from __future__ import annotations

import json
import re
import socket
import time
from pathlib import Path

from .base import CommandResult, ExecutionError
from .telnet import TelnetCollector
from ..policy import validate_commands
from ..write_policy import validate_write_commands
from ..write_executor import _cli_error

PROMPT = re.compile(r"(?:^|\n)[\w.:/()@-]+[>#]\s*$")
LOGIN = re.compile(r"(?:username|login|password):\s*$", re.I)
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def credential(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        username, password = value["username"], value["password"]
        if not isinstance(username, str) or not isinstance(password, str) or not password:
            raise ValueError()
        if any(c in username + password for c in "\r\n\x00"):
            raise ValueError()
        return username, password
    except (OSError, ValueError, KeyError, TypeError):
        raise ExecutionError("Native collector credential is unavailable or invalid.") from None


class TelnetSession:
    def __init__(self, host, timeout):
        self.deadline = time.monotonic() + timeout
        self.socket = socket.create_connection((host, 23), timeout=min(timeout, 10))
        self.state = "data"
        self.verb = 0
        self.received = 0

    def close(self):
        self.socket.close()

    def send(self, value):
        self.socket.sendall(value.encode("utf-8").replace(b"\xff", b"\xff\xff") + b"\r\n")

    def decode(self, raw):
        output = bytearray()
        for byte in raw:
            if self.state == "data":
                if byte == 255:
                    self.state = "iac"
                else:
                    output.append(byte)
            elif self.state == "iac":
                if byte == 255:
                    output.append(byte)
                    self.state = "data"
                elif byte in (251, 252, 253, 254):
                    self.verb = byte
                    self.state = "option"
                elif byte == 250:
                    self.state = "sub"
                else:
                    self.state = "data"
            elif self.state == "option":
                if self.verb in (251, 253):
                    self.socket.sendall(bytes((255, 254 if self.verb == 251 else 252, byte)))
                self.state = "data"
            elif self.state == "sub":
                if byte == 255:
                    self.state = "sub_iac"
            elif self.state == "sub_iac":
                self.state = "data" if byte == 240 else "sub"
        return output.decode("utf-8", errors="replace").replace("\r", "").replace("\x00", "")

    def read(self, *, login=False):
        output = ""
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise ExecutionError("Device session timed out.")
            self.socket.settimeout(remaining)
            raw = self.socket.recv(65536)
            if not raw:
                raise ExecutionError("Device closed the session before a complete response.")
            self.received += len(raw)
            if self.received > 4 * 1024 * 1024:
                raise ExecutionError("Device response exceeded the session size limit.")
            output += self.decode(raw)
            output = ANSI.sub("", output)
            if "--More--" in output:
                output = output.replace("--More--", "")
                self.socket.sendall(b" ")
            output = re.sub(r"[^\n]\x08", "", output)
            if PROMPT.search(output) or (login and LOGIN.search(output)):
                return output

    def authenticate(self, username, password):
        response = self.read(login=True)
        if PROMPT.search(response):
            return response
        if re.search(r"(?:username|login):\s*$", response, re.I):
            self.send(username)
            response = self.read(login=True)
        if re.search(r"password:\s*$", response, re.I):
            self.send(password)
            response = self.read(login=True)
        if not PROMPT.search(response) or _cli_error(response, ""):
            raise ExecutionError("Device authentication failed.")
        return response


def execute(plan, path, timeout, *, write=False, enable_path=None):
    username, password = credential(path)
    secrets = [password]
    session = None
    try:
        session = TelnetSession(plan.device.management_ip, timeout)
        prompt = session.authenticate(username, password)
        if write and prompt.rstrip().endswith(">"):
            if not enable_path:
                raise ExecutionError("Privileged mode requires a configured enable credential.")
            _, enable_password = credential(enable_path)
            secrets.append(enable_password)
            session.send("enable")
            prompt = session.read(login=True)
            if LOGIN.search(prompt):
                session.send(enable_password)
                prompt = session.read(login=True)
            if not PROMPT.search(prompt) or not prompt.rstrip().endswith("#"):
                raise ExecutionError("Device privileged-mode authentication failed.")
        sections = []
        error = ""
        for command in plan.commands:
            session.send(command)
            response = session.read()
            for secret in secrets:
                response = response.replace(secret, "[REDACTED]")
            sections.append(f"===== {command} =====\n{response}")
            error = _cli_error(response, "")
            if error:
                break
        return CommandResult(
            device_id=plan.device.device_id, hostname=plan.device.hostname,
            management_ip=plan.device.management_ip, purpose=plan.purpose,
            commands=plan.commands, stdout="\n".join(sections), stderr=error,
            returncode=1 if error else 0,
        )
    except (OSError, UnicodeError):
        raise ExecutionError("Device transport failed or timed out.") from None
    finally:
        if session:
            session.close()


class NativeTelnetCollector(TelnetCollector):
    def run(self, plan, *, credential_path):
        if not self.supports(plan.device) or not plan.read_only:
            raise ExecutionError("Native read-only collector requires an explicit Telnet read plan.")
        validate_commands(plan.device.vendor, plan.commands)
        return execute(plan, credential_path, self.timeout_seconds)


class NativeTelnetWriteExecutor:
    def __init__(self, *, timeout_seconds=90):
        self.timeout_seconds = timeout_seconds

    def run(self, plan, *, credential_path, enable_credential_path=None):
        if plan.read_only or plan.device.access_method != "telnet":
            raise ExecutionError("Native write executor requires an explicit Telnet change plan.")
        validate_write_commands(plan.commands)
        return execute(plan, credential_path, self.timeout_seconds, write=True,
                       enable_path=enable_credential_path)
