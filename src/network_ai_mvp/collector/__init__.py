from __future__ import annotations

from .base import CollectorAdapter, CollectorRegistry, CommandResult, ExecutionError
from .queue import CollectionJobSnapshot, CollectionQueue
from .telnet import TelnetCollector

__all__ = [
    "CollectorAdapter",
    "CollectorRegistry",
    "CollectionJobSnapshot",
    "CollectionQueue",
    "CommandResult",
    "ExecutionError",
    "TelnetCollector",
]
