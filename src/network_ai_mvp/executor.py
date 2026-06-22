from __future__ import annotations

from .collector.base import CommandResult, ExecutionError
from .collector.telnet import DEFAULT_TELNET_SCRIPT, TelnetCollector


class PowerShellTelnetReadOnlyExecutor(TelnetCollector):
    """Backward-compatible name for the Telnet collector."""


__all__ = [
    "CommandResult",
    "DEFAULT_TELNET_SCRIPT",
    "ExecutionError",
    "PowerShellTelnetReadOnlyExecutor",
]
