from __future__ import annotations

import html
import re
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .audit import append_audit_event, new_audit_event, read_audit_events, redact_text
from .credentials import CredentialMappingError, resolve_credential_path
from .diagnostics import assess_device_risks, summarize_findings
from .executor import CommandResult, PowerShellTelnetReadOnlyExecutor
from .inventory import InventoryError, get_device, load_devices
from .models import CommandPlan, Device
from .neighbors import get_neighbors_for_device
from .observations import (
    find_latest_port,
    latest_ports,
    read_latest_observation,
    store_collection_observation,
)
from .policy import CommandPolicyError, allowed_purposes, build_command_plan
from .search import search_network_state

DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "inventory" / "devices.csv"
DEFAULT_BACKBONE_NEIGHBORS = Path(__file__).resolve().parents[2] / "inventory" / "backbone_neighbors.json"
DEFAULT_AUDIT_LOG = Path(__file__).resolve().parents[2] / "logs" / "collection_audit.jsonl"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    inventory_path: str | Path = DEFAULT_INVENTORY,
    *,
    backbone_neighbors_path: str | Path = DEFAULT_BACKBONE_NEIGHBORS,
    audit_log_path: str | Path = DEFAULT_AUDIT_LOG,
    data_dir: str | Path = DEFAULT_DATA_DIR,
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

    @app.get("/monitoring", include_in_schema=False)
    def monitoring():
        return FileResponse(STATIC_DIR / "monitoring.html")

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

    @app.get("/devices/{device_id}/neighbors")
    def device_neighbors(device_id: str):
        try:
            device = get_device(load_devices(inventory_path), device_id)
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        neighbors = get_neighbors_for_device(backbone_neighbors_path, device.device_id)
        return {
            "device_id": device.device_id,
            "hostname": device.hostname,
            "reference_note": "Reference only. Re-check live CDP/LLDP before acting.",
            "neighbors": [asdict(neighbor) for neighbor in neighbors],
        }

    @app.get("/vendors/{vendor}/purposes")
    def purposes(vendor: str) -> dict[str, tuple[str, ...]]:
        return {"purposes": allowed_purposes(vendor)}

    @app.get("/audit-log")
    def audit_log(limit: int = 100):
        bounded_limit = min(max(limit, 1), 500)
        return {"events": read_audit_events(audit_log_path, limit=bounded_limit)}

    @app.get("/devices/{device_id}/ports/latest")
    def device_ports_latest(device_id: str):
        try:
            device = get_device(load_devices(inventory_path), device_id)
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        observation = read_latest_observation(data_dir, device.device_id)
        if not observation:
            return {
                "device": _public_device(device),
                "data_available": False,
                "message": "No stored parsed observation yet. Run a read-only collection first.",
                "summary": {},
                "ports": [],
            }
        return {
            "device": _public_device(device),
            "data_available": True,
            "timestamp": observation.get("timestamp"),
            "purpose": observation.get("purpose"),
            "summary": observation.get("summary", {}),
            "ports": observation.get("ports", []),
        }

    @app.get("/devices/{device_id}/ports/{interface:path}/latest")
    def device_port_latest(device_id: str, interface: str):
        try:
            device = get_device(load_devices(inventory_path), device_id)
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        port = find_latest_port(data_dir, device.device_id, interface)
        if not port:
            return {
                "device": _public_device(device),
                "interface": interface,
                "data_available": False,
                "message": "No stored parsed observation for this port yet.",
                "port": None,
            }
        return {
            "device": _public_device(device),
            "interface": port.get("interface"),
            "data_available": True,
            "port": port,
        }

    @app.get("/search")
    def search(q: str = ""):
        return {
            "query": q,
            "results": search_network_state(
                query=q,
                inventory_path=inventory_path,
                observations_dir=data_dir,
                backbone_neighbors_path=backbone_neighbors_path,
            ),
        }

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

        if plan.device.access_method != "telnet":
            error_summary = (
                f"Device {plan.device.device_id} access_method is {plan.device.access_method}; "
                "read-only collect requires explicit Telnet MVP access."
            )
            _write_failure_audit(
                audit_log_path,
                plan=plan,
                device_id=device_id,
                purpose=purpose,
                error_summary=error_summary,
            )
            raise HTTPException(status_code=400, detail=error_summary)

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
        stderr = _readable_powershell_stream(result.stderr)
        error_summary = "" if success else _summarize_error(stderr or result.stdout)
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
        observation = None
        if success:
            observation = store_collection_observation(
                data_dir,
                device=plan.device,
                result=result,
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
            "stderr": redact_text(stderr),
            "error_summary": error_summary,
            "observation_stored": observation is not None,
            "parsed_summary": observation.get("summary") if observation else {},
            "parsed_ports": observation.get("ports") if observation else [],
        }

    @app.post("/devices/{device_id}/check")
    def device_check(device_id: str):
        try:
            device = get_device(load_devices(inventory_path), device_id)
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if device.access_method != "telnet":
            error_summary = (
                f"Device {device.device_id} access_method is {device.access_method}; "
                "one-click CHECK requires explicit read-only Telnet MVP access."
            )
            _write_failure_audit(
                audit_log_path,
                device_id=device_id,
                purpose="check",
                error_summary=error_summary,
            )
            raise HTTPException(status_code=400, detail=error_summary)

        purposes = tuple(
            purpose
            for purpose in ("interfaces", "endpoints", "topology", "switching")
            if purpose in allowed_purposes(device.vendor)
        )
        plans = [build_command_plan(device, purpose) for purpose in purposes]
        try:
            credential_path = credential_resolver(device.credential_ref)
        except (CredentialMappingError, OSError, RuntimeError) as exc:
            error_summary = _summarize_error(str(exc))
            _write_failure_audit(
                audit_log_path,
                device_id=device_id,
                purpose="check",
                error_summary=error_summary,
            )
            raise HTTPException(status_code=500, detail=error_summary) from exc

        results: list[CommandResult] = []
        for plan in plans:
            try:
                result = command_executor.run(plan, credential_path=credential_path)
            except (OSError, RuntimeError) as exc:
                error_summary = _summarize_error(str(exc))
                _write_failure_audit(
                    audit_log_path,
                    plan=plan,
                    device_id=device_id,
                    purpose=plan.purpose,
                    error_summary=error_summary,
                )
                raise HTTPException(status_code=500, detail=error_summary) from exc

            stderr = _readable_powershell_stream(result.stderr)
            success = result.returncode == 0
            error_summary = "" if success else _summarize_error(stderr or result.stdout)
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
            if not success:
                return _check_response(
                    device=device,
                    purposes=purposes,
                    commands=_unique_commands(plans),
                    results=results + [result],
                    success=False,
                    error_summary=error_summary,
                    observation=None,
                )
            results.append(
                CommandResult(
                    device_id=result.device_id,
                    hostname=result.hostname,
                    management_ip=result.management_ip,
                    purpose=result.purpose,
                    commands=result.commands,
                    stdout=redact_text(result.stdout),
                    stderr=redact_text(stderr),
                    returncode=result.returncode,
                )
            )

        combined = CommandResult(
            device_id=device.device_id,
            hostname=device.hostname,
            management_ip=device.management_ip,
            purpose="check",
            commands=_unique_commands(plans),
            stdout="\n".join(result.stdout for result in results if result.stdout),
            stderr="\n".join(result.stderr for result in results if result.stderr),
            returncode=0,
        )
        observation = store_collection_observation(
            data_dir,
            device=device,
            result=combined,
        )
        return _check_response(
            device=device,
            purposes=purposes,
            commands=combined.commands,
            results=results,
            success=True,
            error_summary="",
            observation=observation,
        )

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


def _unique_commands(plans: list[CommandPlan]) -> tuple[str, ...]:
    commands: list[str] = []
    seen: set[str] = set()
    for plan in plans:
        for command in plan.commands:
            if command not in seen:
                seen.add(command)
                commands.append(command)
    return tuple(commands)


def _check_response(
    *,
    device: Device,
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
        "device": _public_device(device),
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
        "check_items": _build_check_items(success=success, ports=ports, summary=summary, error_summary=error_summary),
    }


def _build_check_items(
    *,
    success: bool,
    ports: object,
    summary: object,
    error_summary: str,
) -> list[dict[str, str]]:
    if not success:
        message = error_summary or "Read-only collection failed."
        return [
            _check_item("low_speed", "저속 협상 포트 자동 탐지", "fail", message),
            _check_item("high_errors", "CRC/error 많은 포트 탐지", "fail", message),
            _check_item("uplink_lacp_trunk", "uplink/LACP/trunk 이상 탐지", "fail", message),
            _check_item("ip_mac_port", "IP-MAC-Port 자동 추적", "fail", message),
            _check_item("topology_mismatch", "구성도와 실제 연결 상태 불일치 탐지", "fail", message),
        ]

    port_rows = ports if isinstance(ports, list) else []
    summary_map = summary if isinstance(summary, dict) else {}
    low_speed = [port for port in port_rows if _port_low_speed(port)]
    high_errors = [port for port in port_rows if _port_high_errors(port)]
    endpoint_ports = [
        port
        for port in port_rows
        if isinstance(port, dict) and (port.get("endpoint_ips") or port.get("endpoint_macs"))
    ]
    neighbor_ports = [
        port
        for port in port_rows
        if isinstance(port, dict) and (port.get("neighbor_name") or port.get("neighbor_ip"))
    ]

    items = [
        _check_item(
            "low_speed",
            "저속 협상 포트 자동 탐지",
            "warn" if low_speed else "ok",
            _port_list(low_speed) if low_speed else "저속으로 연결된 포트가 수집 결과에서 발견되지 않았습니다.",
        ),
        _check_item(
            "high_errors",
            "CRC/error 많은 포트 탐지",
            "warn" if high_errors else "ok",
            _port_list(high_errors, include_errors=True) if high_errors else "높은 오류 카운터 포트가 수집 결과에서 발견되지 않았습니다.",
        ),
        _check_item(
            "uplink_lacp_trunk",
            "uplink/LACP/trunk 이상 탐지",
            "unknown",
            "read-only switching/topology 명령은 수집했지만, LACP/trunk 자동 판정 파서는 아직 MVP 범위 밖입니다.",
        ),
        _check_item(
            "ip_mac_port",
            "IP-MAC-Port 자동 추적",
            "ok" if endpoint_ports else "unknown",
            f"{len(endpoint_ports)}개 포트에서 IP/MAC 상관관계를 확인했습니다."
            if endpoint_ports
            else "MAC/ARP 상관관계가 수집 결과에서 확인되지 않았습니다.",
        ),
        _check_item(
            "topology_mismatch",
            "구성도와 실제 연결 상태 불일치 탐지",
            "ok" if neighbor_ports else "unknown",
            f"{len(neighbor_ports)}개 포트에서 live neighbor 관측값을 확인했습니다. 문서 대비 자동 비교는 다음 단계입니다."
            if neighbor_ports
            else "live LLDP/CDP neighbor 관측값이 부족해 문서 대비 불일치를 판정하지 않았습니다.",
        ),
    ]
    if not port_rows and int(summary_map.get("total_ports") or 0) == 0:
        for item in items[:2]:
            item["status"] = "unknown"
            item["detail"] = "수집은 성공했지만 파싱 가능한 포트 상태가 없습니다."
    return items


def _check_item(key: str, label: str, status: str, detail: str) -> dict[str, str]:
    return {"key": key, "label": label, "status": status, "detail": detail}


def _port_low_speed(port: object) -> bool:
    return (
        isinstance(port, dict)
        and port.get("status") == "connected"
        and isinstance(port.get("speed_mbps"), int)
        and int(port["speed_mbps"]) < 1000
    )


def _port_high_errors(port: object) -> bool:
    if not isinstance(port, dict):
        return False
    return max(
        int(port.get("fcs_errors") or 0),
        int(port.get("rx_errors") or 0),
        int(port.get("runts") or 0),
        int(port.get("tx_errors") or 0),
    ) >= 1000


def _port_list(ports: list[object], *, include_errors: bool = False) -> str:
    rows = []
    for port in ports[:12]:
        if not isinstance(port, dict):
            continue
        base = (
            f"{port.get('interface')}: status={port.get('status') or '-'}, "
            f"vlan={port.get('vlan') or '-'}, speed={port.get('speed') or '-'}"
        )
        if include_errors:
            base += (
                f", FCS={port.get('fcs_errors') or 0}, Rx={port.get('rx_errors') or 0}, "
                f"Runts={port.get('runts') or 0}, Tx={port.get('tx_errors') or 0}"
            )
        rows.append(base)
    if len(ports) > 12:
        rows.append(f"... 외 {len(ports) - 12}개")
    return "\n".join(rows)


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
    value = _readable_powershell_stream(value)
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return redact_text(stripped[:300])
    return ""


def _readable_powershell_stream(value: str) -> str:
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
