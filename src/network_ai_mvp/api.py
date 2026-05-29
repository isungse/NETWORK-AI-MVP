from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .audit import append_audit_event, new_audit_event, read_audit_events, redact_text
from .credentials import CredentialMappingError, resolve_credential_path
from .diagnostics import assess_device_risks, summarize_findings
from .executor import PowerShellTelnetReadOnlyExecutor
from .inventory import InventoryError, get_device, load_devices
from .models import CommandPlan, Device
from .policy import CommandPolicyError, allowed_purposes, build_command_plan

DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "inventory" / "devices.csv"
DEFAULT_AUDIT_LOG = Path(__file__).resolve().parents[2] / "logs" / "collection_audit.jsonl"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    inventory_path: str | Path = DEFAULT_INVENTORY,
    *,
    audit_log_path: str | Path = DEFAULT_AUDIT_LOG,
    executor: PowerShellTelnetReadOnlyExecutor | None = None,
    credential_resolver: Callable[[str], str | Path] = resolve_credential_path,
):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError("Install the API dependencies with: pip install -e .[api]") from exc

    app = FastAPI(title="Network AI MVP", version="0.1.0")
    command_executor = executor or PowerShellTelnetReadOnlyExecutor()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "mode": "read-only"}

    @app.get("/devices")
    def devices():
        return [_public_device(device) for device in load_devices(inventory_path)]

    @app.get("/devices/{device_id}")
    def device_detail(device_id: str):
        try:
            return _public_device(get_device(load_devices(inventory_path), device_id))
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/devices/{device_id}/command-plan/{purpose}")
    def command_plan(device_id: str, purpose: str):
        try:
            plan = _build_plan(inventory_path, device_id, purpose)
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except CommandPolicyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _public_command_plan(plan)

    @app.get("/devices/{device_id}/diagnostics")
    def device_diagnostics(device_id: str):
        try:
            device = get_device(load_devices(inventory_path), device_id)
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        findings = assess_device_risks(
            device,
            audit_events=read_audit_events(audit_log_path, limit=100),
        )
        return {
            "device_id": device.device_id,
            "hostname": device.hostname,
            "management_ip": device.management_ip,
            "summary": summarize_findings(findings),
            "findings": [asdict(finding) for finding in findings],
        }

    @app.get("/vendors/{vendor}/purposes")
    def purposes(vendor: str) -> dict[str, tuple[str, ...]]:
        return {"purposes": allowed_purposes(vendor)}

    @app.get("/audit-log")
    def audit_log(limit: int = 100):
        bounded_limit = min(max(limit, 1), 500)
        return {"events": read_audit_events(audit_log_path, limit=bounded_limit)}

    @app.post("/devices/{device_id}/collect/{purpose}")
    def collect(device_id: str, purpose: str):
        try:
            plan = _build_plan(inventory_path, device_id, purpose)
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except CommandPolicyError as exc:
            _write_failure_audit(
                audit_log_path,
                device_id=device_id,
                purpose=purpose,
                error_summary=str(exc),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            credential_path = credential_resolver(plan.device.credential_ref)
            result = command_executor.run(plan, credential_path=credential_path)
        except (CredentialMappingError, OSError, RuntimeError) as exc:
            error_summary = _summarize_error(str(exc))
            _write_failure_audit(
                audit_log_path,
                plan=plan,
                device_id=device_id,
                purpose=purpose,
                error_summary=error_summary,
            )
            raise HTTPException(status_code=500, detail=error_summary) from exc

        success = result.returncode == 0
        error_summary = "" if success else _summarize_error(result.stderr or result.stdout)
        append_audit_event(
            audit_log_path,
            new_audit_event(
                device_id=plan.device.device_id,
                hostname=plan.device.hostname,
                management_ip=plan.device.management_ip,
                purpose=plan.purpose,
                commands=plan.commands,
                success=success,
                returncode=result.returncode,
                error_summary=error_summary,
            ),
        )
        return {
            "device_id": result.device_id,
            "hostname": result.hostname,
            "management_ip": result.management_ip,
            "purpose": result.purpose,
            "commands": result.commands,
            "success": success,
            "returncode": result.returncode,
            "stdout_bytes": len(result.stdout.encode("utf-8")),
            "stderr_bytes": len(result.stderr.encode("utf-8")),
            "stdout": redact_text(result.stdout),
            "stderr": redact_text(result.stderr),
            "error_summary": error_summary,
        }

    return app


def _public_device(device: Device) -> dict[str, str]:
    return {
        "device_id": device.device_id,
        "hostname": device.hostname,
        "management_ip": device.management_ip,
        "vendor": device.vendor,
        "platform": device.platform,
        "role": device.role,
        "access_method": device.access_method,
        "notes": device.notes,
    }


def _public_command_plan(plan: CommandPlan) -> dict[str, object]:
    return {
        "device": _public_device(plan.device),
        "purpose": plan.purpose,
        "commands": plan.commands,
        "read_only": plan.read_only,
    }


def _build_plan(inventory_path: str | Path, device_id: str, purpose: str) -> CommandPlan:
    devices_list = load_devices(inventory_path)
    device = get_device(devices_list, device_id)
    return build_command_plan(device, purpose)


def _write_failure_audit(
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
            error_summary=_summarize_error(error_summary),
        ),
    )


def _summarize_error(value: str) -> str:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return redact_text(stripped[:300])
    return ""
