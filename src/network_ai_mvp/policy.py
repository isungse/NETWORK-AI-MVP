from __future__ import annotations

import re
from collections.abc import Iterable

from .models import CommandPlan, Device


class CommandPolicyError(ValueError):
    pass


READ_ONLY_COMMANDS: dict[str, dict[str, tuple[str, ...]]] = {
    "cisco": {
        "baseline": (
            "terminal length 0",
            "show version",
            "show ip interface brief",
            "show interfaces description",
        ),
        "endpoints": (
            "terminal length 0",
            "show interfaces description",
            "show mac address-table",
            "show ip arp",
        ),
        "topology": (
            "terminal length 0",
            "show cdp neighbors",
            "show cdp neighbors detail",
            "show lldp neighbors",
            "show lldp neighbors detail",
        ),
        "interfaces": (
            "terminal length 0",
            "show interfaces status",
            "show interfaces counters errors",
            "show interfaces description",
        ),
        "switching": (
            "terminal length 0",
            "show etherchannel summary",
            "show interfaces trunk",
            "show spanning-tree",
            "show mac address-table",
            "show ip arp",
            "show vlan brief",
        ),
    },
    "arista": {
        "baseline": (
            "terminal length 0",
            "show hostname",
            "show version",
            "show interfaces status",
            "show interfaces description",
        ),
        "endpoints": (
            "terminal length 0",
            "show interfaces description",
            "show mac address-table",
            "show ip arp",
        ),
        "topology": (
            "terminal length 0",
            "show lldp neighbors",
            "show lldp neighbors detail",
        ),
        "interfaces": (
            "terminal length 0",
            "show interfaces status",
            "show interfaces counters errors",
            "show interfaces description",
        ),
        "switching": (
            "terminal length 0",
            "show port-channel summary",
            "show interfaces switchport",
            "show vlan",
            "show spanning-tree",
            "show mac address-table",
            "show ip arp",
        ),
    },
}

BLOCKED_COMMAND_START = re.compile(
    r"^\s*(configure|conf|interface|shutdown|reload|erase|delete|replace|vlan|"
    r"spanning-tree|switchport|channel-group|router|ip route|write|copy|"
    r"enable|disable|commit|request|bash|run)\b",
    re.IGNORECASE,
)


def build_command_plan(device: Device, purpose: str) -> CommandPlan:
    vendor_commands = READ_ONLY_COMMANDS.get(device.vendor)
    if not vendor_commands:
        raise CommandPolicyError(f"No command policy for vendor: {device.vendor}")

    commands = vendor_commands.get(purpose)
    if not commands:
        raise CommandPolicyError(
            f"Unknown command purpose for {device.vendor}: {purpose}. "
            f"Allowed purposes: {sorted(vendor_commands)}"
        )

    validate_commands(device.vendor, commands)
    return CommandPlan(device=device, purpose=purpose, commands=commands)


def validate_commands(vendor: str, commands: Iterable[str]) -> None:
    allowed = _allowed_command_set(vendor)
    for command in commands:
        normalized = command.strip()
        if BLOCKED_COMMAND_START.search(normalized):
            raise CommandPolicyError(f"Blocked non-read-only command: {command}")
        if normalized not in allowed:
            raise CommandPolicyError(f"Command is not allowlisted for {vendor}: {command}")


def allowed_purposes(vendor: str) -> tuple[str, ...]:
    return tuple(sorted(READ_ONLY_COMMANDS.get(vendor, {})))


def _allowed_command_set(vendor: str) -> set[str]:
    vendor_commands = READ_ONLY_COMMANDS.get(vendor)
    if not vendor_commands:
        raise CommandPolicyError(f"No command policy for vendor: {vendor}")
    return {command for commands in vendor_commands.values() for command in commands}
