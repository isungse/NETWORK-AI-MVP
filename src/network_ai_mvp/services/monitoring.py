from __future__ import annotations

import json
import queue
from datetime import UTC, datetime
from threading import Lock
from typing import Iterator


class MonitoringHub:
    def __init__(self) -> None:
        self._state = _empty_monitoring_state()
        self._subscribers: set[queue.Queue[dict[str, object]]] = set()
        self._lock = Lock()

    def latest(self) -> dict[str, object]:
        with self._lock:
            return dict(self._state)

    def publish(self, response: dict[str, object]) -> None:
        payload = _monitoring_payload(response)
        with self._lock:
            self._state.clear()
            self._state.update(payload)
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            subscriber.put(payload)

    def event_stream(self) -> Iterator[str]:
        subscriber: queue.Queue[dict[str, object]] = queue.Queue()
        with self._lock:
            self._subscribers.add(subscriber)
            snapshot = dict(self._state)
        try:
            yield _sse_event(snapshot)
            while True:
                try:
                    yield _sse_event(subscriber.get(timeout=15))
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with self._lock:
                self._subscribers.discard(subscriber)


def _empty_monitoring_state() -> dict[str, object]:
    return {
        "available": False,
        "updated_at": "",
        "device_id": "",
        "hostname": "",
        "management_ip": "",
        "purpose": "",
        "success": None,
        "text": "Run Collect or CHECK in the main UI to stream the latest server-side result here.",
    }


def _monitoring_payload(response: dict[str, object]) -> dict[str, object]:
    device = response.get("device") if isinstance(response.get("device"), dict) else {}
    device_map = device if isinstance(device, dict) else {}
    device_id = str(response.get("device_id") or device_map.get("device_id") or "")
    hostname = str(response.get("hostname") or device_map.get("hostname") or "")
    management_ip = str(response.get("management_ip") or device_map.get("management_ip") or "")
    purpose = str(response.get("purpose") or "")
    success = response.get("success")
    updated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "available": True,
        "updated_at": updated_at,
        "device_id": device_id,
        "hostname": hostname,
        "management_ip": management_ip,
        "purpose": purpose,
        "success": success,
        "text": _monitoring_text(response),
    }


def _monitoring_text(response: dict[str, object]) -> str:
    device = response.get("device") if isinstance(response.get("device"), dict) else {}
    device_map = device if isinstance(device, dict) else {}
    device_id = response.get("device_id") or device_map.get("device_id") or "-"
    management_ip = response.get("management_ip") or device_map.get("management_ip") or "-"
    lines = [
        f"Device: {device_id} ({management_ip})",
        f"Purpose: {response.get('purpose') or '-'}",
        (
            f"Result: {'success' if response.get('success') else 'failure'}    "
            f"returncode={response.get('returncode')}    "
            f"stdout={response.get('stdout_bytes')} bytes    stderr={response.get('stderr_bytes')} bytes"
        ),
        f"Commands: {' | '.join(str(command) for command in response.get('commands') or [])}",
    ]
    if response.get("error_summary"):
        lines.extend(["", "===== ERROR SUMMARY =====", str(response.get("error_summary"))])
    if response.get("stdout"):
        lines.extend(["", "===== STDOUT =====", str(response.get("stdout"))])
    if response.get("stderr"):
        lines.extend(["", "===== STDERR =====", str(response.get("stderr"))])
    return "\n".join(lines)


def _sse_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
