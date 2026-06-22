from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from ..audit import append_audit_event, new_audit_event, redact_text
from ..collector import CollectionQueue, CollectorRegistry, CommandResult
from ..correlation import build_port_endpoint_trace
from ..credentials import CredentialMappingError
from ..inventory import InventoryError, get_device, load_devices
from ..models import CommandPlan, Device
from ..observations import store_collection_observation
from ..policy import CommandPolicyError, allowed_purposes, build_command_plan
from .check import build_interface_findings
from .collection import (
    check_response,
    collect_plans,
    collector_supports,
    public_job_snapshot,
    readable_powershell_stream,
    summarize_error,
    unique_commands,
    unsupported_collector_message,
    write_failure_audit,
)
from .monitoring import MonitoringHub


class WorkflowError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class CollectionWorkflow:
    def __init__(
        self,
        *,
        inventory_path: str | Path,
        audit_log_path: str | Path,
        data_dir: str | Path,
        command_executor: object,
        collection_queue: CollectionQueue,
        credential_resolver: Callable[[str], str | Path],
        collector_registry: CollectorRegistry,
        monitoring_hub: MonitoringHub,
    ) -> None:
        self.inventory_path = inventory_path
        self.audit_log_path = audit_log_path
        self.data_dir = data_dir
        self.command_executor = command_executor
        self.collection_queue = collection_queue
        self.credential_resolver = credential_resolver
        self.collector_registry = collector_registry
        self.monitoring_hub = monitoring_hub

    def collect(self, device_id: str, purpose: str) -> dict[str, object]:
        plan = self._build_plan_or_fail(device_id, purpose)
        self._require_supported(plan.device, device_id=device_id, purpose=purpose, action="read-only collect", plan=plan)
        credential_path = self._credential_or_fail(plan.device, device_id=device_id, purpose=purpose, plan=plan)

        try:
            result = self.command_executor.run(plan, credential_path=credential_path)
        except (CredentialMappingError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            error_summary = summarize_error(str(exc))
            write_failure_audit(
                self.audit_log_path,
                plan=plan,
                device_id=device_id,
                purpose=purpose,
                error_summary=error_summary,
            )
            raise WorkflowError(500, error_summary) from exc

        response = self._collection_response(plan, result)
        self.monitoring_hub.publish(response)
        return response

    def enqueue_collect(self, device_id: str, purpose: str) -> dict[str, object]:
        plan = self._build_plan_or_fail(device_id, purpose)
        self._require_supported(plan.device, device_id=device_id, purpose=purpose, action="queued read-only collect", plan=plan)
        credential_path = self._credential_or_fail(plan.device, device_id=device_id, purpose=purpose, plan=plan)
        snapshot = self.collection_queue.submit(
            adapter=self.command_executor,
            device=plan.device,
            plans=(plan,),
            credential_path=credential_path,
        )
        return public_job_snapshot(snapshot)

    def check(self, device_id: str) -> dict[str, object]:
        device = self._device_or_fail(device_id)
        self._require_supported(device, device_id=device_id, purpose="check", action="one-click CHECK")
        purposes, plans = self._check_plans(device)
        credential_path = self._credential_or_fail(device, device_id=device_id, purpose="check")

        try:
            collected_results = collect_plans(self.command_executor, device, plans, credential_path=credential_path)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            error_summary = summarize_error(str(exc))
            write_failure_audit(
                self.audit_log_path,
                device_id=device_id,
                purpose="check",
                error_summary=error_summary,
            )
            raise WorkflowError(500, error_summary) from exc

        results: list[CommandResult] = []
        for result in collected_results:
            stderr = readable_powershell_stream(result.stderr)
            success = result.returncode == 0
            error_summary = "" if success else summarize_error(stderr or result.stdout)
            append_audit_event(
                self.audit_log_path,
                new_audit_event(
                    device_id=result.device_id,
                    hostname=result.hostname,
                    management_ip=result.management_ip,
                    purpose=result.purpose,
                    commands=result.commands,
                    success=success,
                    returncode=result.returncode,
                    error_summary=error_summary,
                ),
            )
            if not success:
                response = check_response(
                    device=device,
                    collector_registry=self.collector_registry,
                    purposes=purposes,
                    commands=unique_commands(plans),
                    results=results + [result],
                    success=False,
                    error_summary=error_summary,
                    observation=None,
                )
                self.monitoring_hub.publish(response)
                return response
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
            commands=unique_commands(plans),
            stdout="\n".join(result.stdout for result in results if result.stdout),
            stderr="\n".join(result.stderr for result in results if result.stderr),
            returncode=0,
        )
        observation = store_collection_observation(
            self.data_dir,
            device=device,
            result=combined,
        )
        response = check_response(
            device=device,
            collector_registry=self.collector_registry,
            purposes=purposes,
            commands=combined.commands,
            results=results,
            success=True,
            error_summary="",
            observation=observation,
        )
        self.monitoring_hub.publish(response)
        return response

    def enqueue_check(self, device_id: str) -> dict[str, object]:
        device = self._device_or_fail(device_id)
        self._require_supported(device, device_id=device_id, purpose="check", action="queued one-click CHECK")
        _purposes, plans = self._check_plans(device)
        credential_path = self._credential_or_fail(device, device_id=device_id, purpose="check")
        snapshot = self.collection_queue.submit(
            adapter=self.command_executor,
            device=device,
            plans=plans,
            credential_path=credential_path,
        )
        return public_job_snapshot(snapshot)

    def _collection_response(self, plan: CommandPlan, result: CommandResult) -> dict[str, object]:
        success = result.returncode == 0
        stderr = readable_powershell_stream(result.stderr)
        error_summary = "" if success else summarize_error(stderr or result.stdout)
        append_audit_event(
            self.audit_log_path,
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
                self.data_dir,
                device=plan.device,
                result=result,
            )
        response = {
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
            "interface_findings": build_interface_findings(observation.get("ports") if observation else []),
        }
        if success and plan.purpose == "port-endpoints":
            response["port_endpoint_trace"] = build_port_endpoint_trace(result.stdout, self.data_dir)
        return response

    def _build_plan_or_fail(self, device_id: str, purpose: str) -> CommandPlan:
        try:
            device = self._device_or_fail(device_id)
            return build_command_plan(device, purpose)
        except CommandPolicyError as exc:
            write_failure_audit(
                self.audit_log_path,
                device_id=device_id,
                purpose=purpose,
                error_summary=str(exc),
            )
            raise WorkflowError(400, str(exc)) from exc

    def _device_or_fail(self, device_id: str) -> Device:
        try:
            return get_device(load_devices(self.inventory_path), device_id)
        except InventoryError as exc:
            raise WorkflowError(404, str(exc)) from exc

    def _credential_or_fail(
        self,
        device: Device,
        *,
        device_id: str,
        purpose: str,
        plan: CommandPlan | None = None,
    ) -> str | Path:
        try:
            return self.credential_resolver(device.credential_ref)
        except (CredentialMappingError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            error_summary = summarize_error(str(exc))
            write_failure_audit(
                self.audit_log_path,
                plan=plan,
                device_id=device_id,
                purpose=purpose,
                error_summary=error_summary,
            )
            raise WorkflowError(500, error_summary) from exc

    def _require_supported(
        self,
        device: Device,
        *,
        device_id: str,
        purpose: str,
        action: str,
        plan: CommandPlan | None = None,
    ) -> None:
        if collector_supports(self.command_executor, self.collector_registry, device):
            return
        error_summary = unsupported_collector_message(device, action=action)
        write_failure_audit(
            self.audit_log_path,
            plan=plan,
            device_id=device_id,
            purpose=purpose,
            error_summary=error_summary,
        )
        raise WorkflowError(400, error_summary)

    def _check_plans(self, device: Device) -> tuple[tuple[str, ...], list[CommandPlan]]:
        purposes = tuple(
            purpose
            for purpose in ("interfaces", "endpoints", "topology", "switching")
            if purpose in allowed_purposes(device.vendor)
        )
        return purposes, [build_command_plan(device, purpose) for purpose in purposes]
