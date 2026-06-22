from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Literal, Sequence
from uuid import uuid4

from ..models import CommandPlan, Device
from .base import CollectorAdapter, CommandResult

CollectionStatus = Literal["queued", "running", "succeeded", "failed"]


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CollectionJobSnapshot:
    job_id: str
    status: CollectionStatus
    device_id: str
    purposes: tuple[str, ...]
    commands: tuple[str, ...]
    created_at: str
    updated_at: str
    results: tuple[CommandResult, ...] = ()
    error: str = ""


@dataclass
class _CollectionJob:
    job_id: str
    device: Device
    plans: tuple[CommandPlan, ...]
    status: CollectionStatus = "queued"
    created_at: str = field(default_factory=_timestamp)
    updated_at: str = field(default_factory=_timestamp)
    results: tuple[CommandResult, ...] = ()
    error: str = ""

    def snapshot(self) -> CollectionJobSnapshot:
        return CollectionJobSnapshot(
            job_id=self.job_id,
            status=self.status,
            device_id=self.device.device_id,
            purposes=tuple(plan.purpose for plan in self.plans),
            commands=_unique_commands(self.plans),
            created_at=self.created_at,
            updated_at=self.updated_at,
            results=self.results,
            error=self.error,
        )


class CollectionQueue:
    def __init__(self, *, max_workers: int = 8) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="network-ai-collector")
        self._jobs: dict[str, _CollectionJob] = {}
        self._futures: dict[str, Future[None]] = {}
        self._lock = Lock()

    def submit(
        self,
        *,
        adapter: CollectorAdapter,
        device: Device,
        plans: Sequence[CommandPlan],
        credential_path: str | Path,
    ) -> CollectionJobSnapshot:
        job = _CollectionJob(job_id=uuid4().hex, device=device, plans=tuple(plans))
        with self._lock:
            self._jobs[job.job_id] = job
            self._futures[job.job_id] = self._executor.submit(
                self._run_job,
                job.job_id,
                adapter,
                credential_path,
            )
            return job.snapshot()

    def get(self, job_id: str) -> CollectionJobSnapshot | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot() if job else None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)

    def _run_job(self, job_id: str, adapter: CollectorAdapter, credential_path: str | Path) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            job.updated_at = _timestamp()
        try:
            results = tuple(adapter.collect(job.device, job.plans, credential_path=credential_path))
        except Exception as exc:  # noqa: BLE001 - queue stores adapter failure for API/UI polling.
            with self._lock:
                job.status = "failed"
                job.error = str(exc)
                job.updated_at = _timestamp()
            return

        with self._lock:
            job.status = "succeeded"
            job.results = results
            job.updated_at = _timestamp()


def _unique_commands(plans: Sequence[CommandPlan]) -> tuple[str, ...]:
    commands: list[str] = []
    seen: set[str] = set()
    for plan in plans:
        for command in plan.commands:
            if command not in seen:
                seen.add(command)
                commands.append(command)
    return tuple(commands)
