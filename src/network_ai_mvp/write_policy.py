from __future__ import annotations

import re
from typing import Literal

from .models import CommandPlan, Device

AdminState = Literal["shutdown", "no shutdown"]

INTERFACE_PATTERN = re.compile(
    r"^(?:Et|Ethernet|Gi|GigabitEthernet|Te|TenGigabitEthernet|Fa|FastEthernet)\d+(?:/\d+){0,3}$",
    re.IGNORECASE,
)


class WritePolicyError(ValueError):
    pass


def build_interface_admin_change_plan(
    device: Device,
    *,
    interface: str,
    desired_state: AdminState,
) -> CommandPlan:
    interface_name = interface.strip()
    if not INTERFACE_PATTERN.match(interface_name):
        raise WritePolicyError(f"Interface is not eligible for write changes: {interface}")
    if desired_state not in {"shutdown", "no shutdown"}:
        raise WritePolicyError(f"Unsupported interface admin state: {desired_state}")

    commands = (
        "configure terminal",
        f"interface {interface_name}",
        desired_state,
        "end",
    )
    validate_write_commands(commands)
    return CommandPlan(
        device=device,
        purpose="interface-admin-state",
        commands=commands,
        read_only=False,
    )


def validate_write_commands(commands: tuple[str, ...]) -> None:
    if len(commands) != 4:
        raise WritePolicyError("Write change must use the fixed interface admin-state command shape.")
    if commands[0] != "configure terminal" or commands[3] != "end":
        raise WritePolicyError("Write change must enter and leave configuration mode explicitly.")
    if not commands[1].startswith("interface "):
        raise WritePolicyError("Write change must target exactly one interface.")
    interface = commands[1].removeprefix("interface ").strip()
    if not INTERFACE_PATTERN.match(interface):
        raise WritePolicyError(f"Interface is not eligible for write changes: {interface}")
    if commands[2] not in {"shutdown", "no shutdown"}:
        raise WritePolicyError(f"Unsupported write command: {commands[2]}")
