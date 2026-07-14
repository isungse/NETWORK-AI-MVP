from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
import os
from pathlib import Path
import subprocess
from typing import Callable

from .audit import read_audit_events
from .collector import CollectionQueue, CollectorRegistry
from .credentials import resolve_credential_path
from .diagnostics import assess_device_risks, summarize_findings
from .executor import PowerShellTelnetReadOnlyExecutor
from .inventory import InventoryError, get_device, load_devices
from .models import CommandPlan, Device
from .neighbors import get_neighbors_for_device
from .observations import find_latest_port, read_latest_observation, read_latest_port_observation
from .port_diagnostics import build_port_connection_diagnostic, ping_target
from .policy import CommandPolicyError, allowed_purposes, build_command_plan
from .search import search_network_state
from .services.collection import public_command_plan, public_device, public_job_snapshot
from .services.collection_workflow import CollectionWorkflow, WorkflowError
from .services.monitoring import MonitoringHub
from .services.topology import build_topology

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IS_VERCEL = bool(os.environ.get("VERCEL"))
RUNTIME_ROOT = Path(
    os.environ.get("NETWORK_AI_RUNTIME_DIR")
    or ("/tmp/network-ai-mvp" if IS_VERCEL else PROJECT_ROOT)
)
DEFAULT_INVENTORY = PROJECT_ROOT / "inventory" / "devices.csv"
DEFAULT_BACKBONE_NEIGHBORS = PROJECT_ROOT / "inventory" / "backbone_neighbors.json"
DEFAULT_AUDIT_LOG = RUNTIME_ROOT / "logs" / "collection_audit.jsonl"
DEFAULT_DATA_DIR = RUNTIME_ROOT / "data"
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_COLLECTOR_REGISTRY = CollectorRegistry((PowerShellTelnetReadOnlyExecutor(),))


def create_app(
    inventory_path: str | Path = DEFAULT_INVENTORY,
    *,
    backbone_neighbors_path: str | Path = DEFAULT_BACKBONE_NEIGHBORS,
    audit_log_path: str | Path = DEFAULT_AUDIT_LOG,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    executor: PowerShellTelnetReadOnlyExecutor | None = None,
    credential_resolver: Callable[[str], str | Path] = resolve_credential_path,
    ping_executor: Callable[[str], dict[str, object]] | None = None,
):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import FileResponse, StreamingResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError("Install the API dependencies with: pip install -e .[api]") from exc

    command_executor = executor or PowerShellTelnetReadOnlyExecutor()
    run_ping = ping_executor or ping_target
    collection_queue = CollectionQueue()
    monitoring_hub = MonitoringHub()
    collection_workflow = CollectionWorkflow(
        inventory_path=inventory_path,
        audit_log_path=audit_log_path,
        data_dir=data_dir,
        command_executor=command_executor,
        collection_queue=collection_queue,
        credential_resolver=credential_resolver,
        collector_registry=DEFAULT_COLLECTOR_REGISTRY,
        monitoring_hub=monitoring_hub,
    )

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            collection_queue.shutdown()

    app = FastAPI(title="Network AI MVP", version="0.1.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index(): return FileResponse(STATIC_DIR / "index.html")

    @app.get("/operations", include_in_schema=False)
    def operations(): return FileResponse(STATIC_DIR / "operations.html")

    @app.get("/monitoring", include_in_schema=False)
    def monitoring(): return FileResponse(STATIC_DIR / "monitoring.html")

    @app.get("/monitoring/latest")
    def monitoring_latest(): return monitoring_hub.latest()

    @app.get("/events/monitoring", include_in_schema=False)
    def monitoring_events(): return StreamingResponse(monitoring_hub.event_stream(), media_type="text/event-stream")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "mode": "read-only",
            "monitoring_transport": "poll" if IS_VERCEL else "sse",
        }

    @app.get("/devices")
    def devices():
        try:
            return [public_device(device, DEFAULT_COLLECTOR_REGISTRY) for device in load_devices(inventory_path)]
        except InventoryError as exc:
            raise HTTPException(status_code=503, detail=f"Inventory unavailable: {exc}") from exc

    @app.get("/devices/{device_id}")
    def device_detail(device_id: str):
        try:
            return public_device(get_device(load_devices(inventory_path), device_id), DEFAULT_COLLECTOR_REGISTRY)
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
        return public_command_plan(plan, DEFAULT_COLLECTOR_REGISTRY)

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

    @app.get("/topology")
    def topology():
        try:
            return build_topology(
                devices=load_devices(inventory_path),
                data_dir=data_dir,
                backbone_neighbors_path=backbone_neighbors_path,
                audit_log_path=audit_log_path,
                collector_registry=DEFAULT_COLLECTOR_REGISTRY,
            )
        except InventoryError as exc:
            raise HTTPException(status_code=503, detail=f"Inventory unavailable: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=f"Topology reference unavailable: {exc}") from exc

    @app.get("/vendors/{vendor}/purposes")
    def purposes(vendor: str) -> dict[str, tuple[str, ...]]: return {"purposes": allowed_purposes(vendor)}

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

        latest_observation = read_latest_observation(data_dir, device.device_id)
        observation = read_latest_port_observation(data_dir, device.device_id)
        if not observation:
            latest_purpose = latest_observation.get("purpose") if latest_observation else None
            latest_timestamp = latest_observation.get("timestamp") if latest_observation else None
            message = (
                f"Latest {latest_purpose} observation contains no parsed port status. "
                "Run a read-only interfaces or CHECK collection."
                if latest_observation
                else "No stored parsed port observation yet. Run a read-only interfaces collection first."
            )
            return {
                "device": public_device(device, DEFAULT_COLLECTOR_REGISTRY),
                "data_available": False,
                "message": message,
                "latest_timestamp": latest_timestamp,
                "latest_purpose": latest_purpose,
                "summary": {},
                "ports": [],
            }
        observation_identity = observation.get("run_id") or (
            observation.get("timestamp"),
            observation.get("purpose"),
        )
        latest_identity = (
            latest_observation.get("run_id")
            or (latest_observation.get("timestamp"), latest_observation.get("purpose"))
            if latest_observation
            else None
        )
        is_latest_observation = bool(latest_observation and observation_identity == latest_identity)
        return {
            "device": public_device(device, DEFAULT_COLLECTOR_REGISTRY),
            "data_available": True,
            "timestamp": observation.get("timestamp"),
            "purpose": observation.get("purpose"),
            "is_latest_observation": is_latest_observation,
            "latest_timestamp": latest_observation.get("timestamp") if latest_observation else None,
            "latest_purpose": latest_observation.get("purpose") if latest_observation else None,
            "message": (
                None
                if is_latest_observation
                else (
                    f"Latest {latest_observation.get('purpose')} observation contains no port data. "
                    f"Showing the last port snapshot from {observation.get('timestamp')}."
                )
            ),
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
                "device": public_device(device, DEFAULT_COLLECTOR_REGISTRY),
                "interface": interface,
                "data_available": False,
                "message": "No stored parsed observation for this port yet.",
                "port": None,
            }
        return {
            "device": public_device(device, DEFAULT_COLLECTOR_REGISTRY),
            "interface": port.get("interface"),
            "data_available": True,
            "port": port,
        }

    @app.get("/devices/{device_id}/port-connection-diagnostic")
    def port_connection_diagnostic(device_id: str, interface: str):
        try:
            get_device(load_devices(inventory_path), device_id)
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return build_port_connection_diagnostic(
            data_dir,
            device_id=device_id,
            interface=interface,
        )

    @app.post("/devices/{device_id}/port-connection-diagnostic/ping")
    def port_connection_ping(device_id: str, interface: str, target_ip: str):
        try:
            get_device(load_devices(inventory_path), device_id)
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        diagnostic = build_port_connection_diagnostic(
            data_dir,
            device_id=device_id,
            interface=interface,
        )
        if not diagnostic.get("data_available"):
            raise HTTPException(status_code=404, detail=str(diagnostic.get("message")))
        observed_ips = {str(value) for value in diagnostic.get("endpoint_ips") or []}
        if target_ip not in observed_ips:
            raise HTTPException(
                status_code=400,
                detail="Ping target must be an IP currently correlated with the selected port.",
            )
        try:
            return run_ping(target_ip)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise HTTPException(status_code=500, detail=f"Ping test failed: {exc}") from exc

    @app.get("/search")
    def search(q: str = ""):
        try:
            results = search_network_state(
                query=q,
                inventory_path=inventory_path,
                observations_dir=data_dir,
                backbone_neighbors_path=backbone_neighbors_path,
            )
        except InventoryError as exc:
            raise HTTPException(status_code=503, detail=f"Inventory unavailable: {exc}") from exc
        return {"query": q, "results": results}

    @app.post("/devices/{device_id}/collect/{purpose}")
    def collect(device_id: str, purpose: str):
        return _workflow_response(collection_workflow.collect, device_id, purpose)

    @app.post("/devices/{device_id}/collect/{purpose}/jobs")
    def enqueue_collect(device_id: str, purpose: str):
        return _workflow_response(collection_workflow.enqueue_collect, device_id, purpose)

    @app.post("/devices/{device_id}/check")
    def device_check(device_id: str):
        return _workflow_response(collection_workflow.check, device_id)

    @app.post("/devices/{device_id}/check/jobs")
    def enqueue_check(device_id: str):
        return _workflow_response(collection_workflow.enqueue_check, device_id)

    @app.get("/collection-jobs/{job_id}")
    def collection_job(job_id: str):
        snapshot = collection_queue.get(job_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail=f"Unknown collection job: {job_id}")
        return public_job_snapshot(snapshot)

    return app


def _build_plan(inventory_path: str | Path, device_id: str, purpose: str) -> CommandPlan:
    return build_command_plan(get_device(load_devices(inventory_path), device_id), purpose)


def _workflow_response(callback, *args):
    try:
        return callback(*args)
    except WorkflowError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
