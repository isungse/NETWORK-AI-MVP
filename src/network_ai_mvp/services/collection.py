from __future__ import annotations

import html
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path

from ..audit import append_audit_event, new_audit_event, redact_text
from ..collector import CollectorRegistry, CommandResult
from ..models import CommandPlan, Device
from .check import build_check_items, build_interface_findings


def public_device(device: Device, collector_registry: CollectorRegistry) -> dict[str, object]:
    return {
        "device_id": device.device_id,
        "hostname": device.hostname,
        "management_ip": device.management_ip,
        "vendor": device.vendor,
        "platform": device.platform,
        "role": device.role,
        "access_method": device.access_method,
        "collectable": collector_registry.supports(device),
        "notes": device.notes,
    }


def public_command_plan(plan: CommandPlan, collector_registry: CollectorRegistry) -> dict[str, object]:
    return {
        "device": public_device(plan.device, collector_registry),
        "purpose": plan.purpose,
        "commands": plan.commands,
        "read_only": plan.read_only,
    }


def public_job_snapshot(snapshot: object) -> dict[str, object]:
    payload = asdict(snapshot) if is_dataclass(snapshot) and not isinstance(snapshot, type) else dict(snapshot)  # type: ignore[arg-type]
    payload["results"] = [
        asdict(result) if is_dataclass(result) and not isinstance(result, type) else result
        for result in payload.get("results", ())
    ]
    return payload


def unique_commands(plans: list[CommandPlan]) -> tuple[str, ...]:
    commands: list[str] = []
    seen: set[str] = set()
    for plan in plans:
        for command in plan.commands:
            if command not in seen:
                seen.add(command)
                commands.append(command)
    return tuple(commands)


def collector_supports(command_executor: object, collector_registry: CollectorRegistry, device: Device) -> bool:
    supports = getattr(command_executor, "supports", None)
    if callable(supports):
        return bool(supports(device))
    return collector_registry.supports(device)


def collect_plans(
    command_executor: object,
    device: Device,
    plans: list[CommandPlan],
    *,
    credential_path: str | Path,
) -> tuple[CommandResult, ...]:
    collect = getattr(command_executor, "collect", None)
    if callable(collect):
        return tuple(collect(device, plans, credential_path=credential_path))

    run = getattr(command_executor, "run")
    return tuple(run(plan, credential_path=credential_path) for plan in plans)


def unsupported_collector_message(device: Device, *, action: str) -> str:
    return (
        f"Device {device.device_id} access_method is {device.access_method}; "
        f"{action} requires a supported read-only collector adapter."
    )


def check_response(
    *,
    device: Device,
    collector_registry: CollectorRegistry,
    purposes: tuple[str, ...],
    commands: tuple[str, ...],
    results: list[CommandResult],
    success: bool,
    error_summary: str,
    observation: dict[str, object] | None,
) -> dict[str, object]:
    stdout = "\n".join(redact_text(result.stdout) for result in results if result.stdout)
    stderr = "\n".join(redact_text(result.stderr) for result in results if result.stderr)
    ports = observation.get("ports", []) if observation else []
    summary = observation.get("summary", {}) if observation else {}
    return {
        "device": public_device(device, collector_registry),
        "purpose": "check",
        "purposes_collected": purposes,
        "commands": commands,
        "success": success,
        "returncode": 0 if success else 1,
        "stdout_bytes": len(stdout.encode("utf-8")),
        "stderr_bytes": len(stderr.encode("utf-8")),
        "stdout": stdout,
        "stderr": stderr,
        "error_summary": error_summary,
        "observation_stored": observation is not None,
        "parsed_summary": summary,
        "parsed_ports": ports,
        "interface_findings": build_interface_findings(ports),
        "check_items": build_check_items(success=success, ports=ports, summary=summary, error_summary=error_summary),
    }


def write_failure_audit(
    audit_log_path: str | Path,
    *,
    device_id: str,
    purpose: str,
    error_summary: str,
    plan: CommandPlan | None = None,
) -> None:
    append_audit_event(
        audit_log_path,
        new_audit_event(
            device_id=plan.device.device_id if plan else device_id,
            hostname=plan.device.hostname if plan else "",
            management_ip=plan.device.management_ip if plan else "",
            purpose=plan.purpose if plan else purpose,
            commands=plan.commands if plan else (),
            success=False,
            returncode=None,
            error_summary=summarize_error(error_summary),
        ),
    )


def summarize_error(value: str) -> str:
    value = readable_powershell_stream(value)
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return redact_text(stripped[:300])
    return ""


def readable_powershell_stream(value: str) -> str:
    if "<S S=\"Error\">" not in value:
        return value

    messages = []
    for match in re.findall(r"<S S=\"Error\">(.*?)</S>", value, flags=re.DOTALL):
        text = html.unescape(match)
        text = text.replace("_x000D__x000A_", "\n")
        stripped = text.strip()
        if stripped:
            messages.append(stripped)
    return "\n".join(messages) if messages else value
