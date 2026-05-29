from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SECRET_FIELD_NAMES = {
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "credential_path",
    "credential_ref",
    "credentials",
    "credential_file",
    "credential_file_path",
    "credentialpath",
}

SECRET_TEXT_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "credential_ref",
    "credential path",
    "credential_path",
    "credential file",
    "credential_file",
    "credentials",
)

ENV_CREDENTIAL_PATTERN = re.compile(r"NETWORK_AI_CREDENTIAL_[A-Z0-9_]+")
WINDOWS_CREDENTIAL_FILE_PATTERN = re.compile(r"[A-Za-z]:\\[^\s'\"]*\.cred\.xml", re.IGNORECASE)
PATH_LIKE_CREDENTIAL_PATTERN = re.compile(r"(?:[^\s'\"]*[\\/])?[^\s'\"]*(?:cred|credential)[^\s'\"]*", re.IGNORECASE)


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    device_id: str
    hostname: str
    management_ip: str
    purpose: str
    commands: tuple[str, ...]
    success: bool
    returncode: int | None
    error_summary: str


def new_audit_event(
    *,
    device_id: str,
    hostname: str,
    management_ip: str,
    purpose: str,
    commands: tuple[str, ...],
    success: bool,
    returncode: int | None,
    error_summary: str = "",
) -> AuditEvent:
    return AuditEvent(
        timestamp=datetime.now(UTC).isoformat(),
        device_id=device_id,
        hostname=hostname,
        management_ip=management_ip,
        purpose=purpose,
        commands=commands,
        success=success,
        returncode=returncode,
        error_summary=redact_text(error_summary),
    )


def append_audit_event(path: str | Path, event: AuditEvent) -> None:
    audit_path = Path(path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    payload = redact_value(asdict(event))
    with audit_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        file_obj.write("\n")


def read_audit_events(path: str | Path, *, limit: int = 100) -> list[dict[str, Any]]:
    audit_path = Path(path)
    if not audit_path.exists():
        return []

    records: list[dict[str, Any]] = []
    with audit_path.open(encoding="utf-8") as file_obj:
        for line in file_obj:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(redact_value(record))
    return records[-limit:]


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SECRET_FIELD_NAMES:
                continue
            else:
                redacted[key] = redact_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_text(value: str) -> str:
    redacted = value
    redacted = ENV_CREDENTIAL_PATTERN.sub("[REDACTED]", redacted)
    redacted = WINDOWS_CREDENTIAL_FILE_PATTERN.sub("[REDACTED_CREDENTIAL_FILE]", redacted)
    for marker in SECRET_TEXT_MARKERS:
        redacted = _redact_marker_and_value(redacted, marker)
    redacted = PATH_LIKE_CREDENTIAL_PATTERN.sub("[REDACTED]", redacted)
    return redacted


def _redact_marker_and_value(value: str, marker: str) -> str:
    pattern = re.compile(
        rf"\b{re.escape(marker)}\b(?:\s*(?:=|:|is|for)?\s*['\"]?[^\s,'\"]+['\"]?)?",
        re.IGNORECASE,
    )
    return pattern.sub("[REDACTED]", value)
