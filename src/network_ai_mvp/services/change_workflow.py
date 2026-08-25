from __future__ import annotations

import hmac
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable
from uuid import uuid4

from ..audit import redact_value
from ..collector.base import CommandResult
from ..credentials import CredentialMappingError
from ..inventory import InventoryError, InventoryRepository
from ..models import CommandPlan, Device
from ..observations import find_latest_port
from ..parsers import short_interface_name
from ..services.collection import readable_powershell_stream, summarize_error
from ..write_policy import AdminState, WritePolicyError, build_interface_admin_change_plan


DISABLED_STATES = {"disabled", "administratively down", "admin-down"}


@dataclass(frozen=True)
class LocalChangeProposal:
    proposal_id: str
    device_id: str
    interface: str
    desired_state: AdminState
    commands: tuple[str, ...]
    created_at: str
    authorization_method: str = "local-approval-code"


class ChangeWorkflowError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class ChangeWorkflow:
    def __init__(
        self,
        *,
        inventory: InventoryRepository,
        data_dir: str | Path,
        audit_log_path: str | Path,
        collection_workflow: object,
        write_executor: object,
        credential_resolver: Callable[[str], str | Path],
        enable_credential_resolver: Callable[[str], str | Path | None],
        enabled: bool,
        approval_token: str,
        proposal_ttl_seconds: int = 300,
    ) -> None:
        self.inventory = inventory
        self.data_dir = Path(data_dir)
        self.audit_log_path = Path(audit_log_path)
        self.collection_workflow = collection_workflow
        self.write_executor = write_executor
        self.credential_resolver = credential_resolver
        self.enable_credential_resolver = enable_credential_resolver
        self.enabled = enabled and bool(approval_token)
        self.approval_token = approval_token
        self.proposal_ttl_seconds = proposal_ttl_seconds
        self._proposals: dict[str, dict[str, object]] = {}

    def capabilities(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "local_only": True,
            "actions": ["shutdown", "no shutdown"] if self.enabled else [],
            "safeguards": [
                "single physical access port only",
                "approval code required for execution",
                "live read-only precheck and postcheck",
                "trunk, uplink, and observed-neighbor ports blocked",
                "running configuration only; write memory is never executed",
            ],
            "message": (
                "Controlled port changes are enabled for this local runtime."
                if self.enabled
                else "Controlled port changes are disabled. Configure the local change gate and approval code."
            ),
        }

    def prepare(
        self,
        *,
        device_id: str,
        interface: str,
        desired_state: str,
    ) -> dict[str, object]:
        self._require_enabled()
        if desired_state not in {"shutdown", "no shutdown"}:
            raise ChangeWorkflowError(400, f"Unsupported desired state: {desired_state}")
        device = self._device(device_id)
        normalized_interface = short_interface_name(interface)
        port = find_latest_port(self.data_dir, device.device_id, normalized_interface)
        if not port:
            raise ChangeWorkflowError(409, "No stored parsed port state is available. Run a live interfaces collection first.")
        self._require_eligible_port(port, desired_state=desired_state)

        try:
            plan: CommandPlan = build_interface_admin_change_plan(
                device,
                interface=normalized_interface,
                desired_state=desired_state,  # type: ignore[arg-type]
            )
        except (PermissionError, WritePolicyError, ValueError) as exc:
            raise ChangeWorkflowError(400, str(exc)) from exc
        proposal = LocalChangeProposal(
            proposal_id=uuid4().hex,
            device_id=device.device_id,
            interface=normalized_interface,
            desired_state=desired_state,  # type: ignore[arg-type]
            commands=plan.commands,
            created_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )

        expires_at = datetime.now(UTC) + timedelta(seconds=self.proposal_ttl_seconds)
        rollback_state: AdminState = "no shutdown" if desired_state == "shutdown" else "shutdown"
        self._proposals[proposal.proposal_id] = {
            "proposal": proposal,
            "plan": plan,
            "expires_at": expires_at,
            "used": False,
            "expected_status": str(port.get("status") or ""),
            "rollback_state": rollback_state,
        }
        self._audit(
            proposal,
            status="prepared",
            rollback_state=rollback_state,
        )
        return {
            "proposal_id": proposal.proposal_id,
            "device_id": device.device_id,
            "hostname": device.hostname,
            "interface": normalized_interface,
            "desired_state": desired_state,
            "commands": list(plan.commands),
            "rollback_commands": ["configure terminal", f"interface {normalized_interface}", rollback_state, "end"],
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            "persistent": False,
            "warning": "This changes running-config only. write memory is not executed.",
        }

    def execute(
        self,
        *,
        proposal_id: str,
        approval_token: str,
    ) -> dict[str, object]:
        self._require_enabled()
        prepared = self._proposals.get(proposal_id)
        if not prepared:
            raise ChangeWorkflowError(404, "Unknown or expired change proposal.")
        if prepared.get("used"):
            raise ChangeWorkflowError(409, "This change proposal has already been used.")
        expires_at = prepared["expires_at"]
        if not isinstance(expires_at, datetime) or datetime.now(UTC) > expires_at:
            self._proposals.pop(proposal_id, None)
            raise ChangeWorkflowError(410, "Change proposal expired. Review the live port state again.")
        if not hmac.compare_digest(approval_token, self.approval_token):
            raise ChangeWorkflowError(403, "Approval code is invalid.")

        proposal = prepared["proposal"]
        plan = prepared["plan"]
        if not isinstance(proposal, LocalChangeProposal):
            raise ChangeWorkflowError(500, "Invalid in-memory proposal state.")
        desired_state = proposal.desired_state

        precheck = self._collect_interfaces(proposal.device_id, phase="precheck")
        fresh_port = find_latest_port(self.data_dir, proposal.device_id, proposal.interface)
        if not fresh_port:
            raise ChangeWorkflowError(409, "Live precheck did not return the selected port.")
        self._require_eligible_port(fresh_port, desired_state=desired_state)

        device = self._device(proposal.device_id)
        # A proposal is single-use before any write attempt. A timeout or transport
        # failure leaves device state uncertain and must require a fresh live review.
        prepared["used"] = True
        try:
            credential_path = self.credential_resolver(device.credential_ref)
            enable_credential_path = self.enable_credential_resolver(device.credential_ref)
            result: CommandResult = self.write_executor.run(
                plan,
                credential_path=credential_path,
                enable_credential_path=enable_credential_path,
            )
        except (CredentialMappingError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            detail = summarize_error(str(exc))
            self._audit(proposal, status="execution-failed", error=detail)
            raise ChangeWorkflowError(500, detail) from exc

        if result.returncode != 0:
            detail = summarize_error(readable_powershell_stream(result.stderr) or result.stdout)
            self._audit(proposal, status="execution-failed", error=detail)
            raise ChangeWorkflowError(502, detail or "Device rejected the controlled port change.")

        postcheck = self._collect_interfaces(proposal.device_id, phase="postcheck")
        verified_port = find_latest_port(self.data_dir, proposal.device_id, proposal.interface)
        verified = bool(verified_port and self._matches_desired_state(verified_port, desired_state))
        status = "executed-verified" if verified else "verification-failed"
        self._audit(
            proposal,
            status=status,
            verified_status=str((verified_port or {}).get("status") or "unknown"),
            rollback_state=str(prepared["rollback_state"]),
        )
        if not verified:
            raise ChangeWorkflowError(
                502,
                "The command completed but the live postcheck did not confirm the requested admin state. Use the rollback plan and verify manually.",
            )
        return {
            "proposal_id": proposal.proposal_id,
            "device_id": proposal.device_id,
            "interface": proposal.interface,
            "desired_state": desired_state,
            "success": True,
            "verified": True,
            "verified_status": verified_port.get("status"),
            "verified_port": verified_port,
            "precheck_timestamp": precheck.get("observation_timestamp"),
            "postcheck_timestamp": postcheck.get("observation_timestamp"),
            "persistent": False,
            "message": "Controlled port change executed and verified. running-config was not saved.",
            "rollback_state": prepared["rollback_state"],
        }

    def _collect_interfaces(self, device_id: str, *, phase: str) -> dict[str, object]:
        try:
            response = self.collection_workflow.collect(device_id, "interfaces")
        except Exception as exc:
            status_code = getattr(exc, "status_code", 500)
            detail = getattr(exc, "detail", str(exc))
            raise ChangeWorkflowError(status_code, f"Live {phase} failed: {detail}") from exc
        if not response.get("success"):
            raise ChangeWorkflowError(502, f"Live {phase} failed: {response.get('error_summary') or 'collection failed'}")
        observation = response.get("parsed_ports") or []
        return {
            "observation_timestamp": next(
                (port.get("source_timestamp") for port in observation if isinstance(port, dict)),
                None,
            )
        }

    def _device(self, device_id: str) -> Device:
        try:
            return self.inventory.get_device(device_id)
        except InventoryError as exc:
            raise ChangeWorkflowError(404, str(exc)) from exc

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise ChangeWorkflowError(403, "Controlled port changes are disabled for this runtime.")

    @staticmethod
    def _require_eligible_port(port: dict[str, object], *, desired_state: str) -> None:
        vlan = str(port.get("vlan") or "").strip().lower()
        if vlan in {"trunk", "routed"}:
            raise ChangeWorkflowError(409, "Trunk and routed ports cannot be changed from the port-control UI.")
        if port.get("neighbor_name") or port.get("neighbor_ip"):
            raise ChangeWorkflowError(409, "Ports with observed network neighbors are protected as possible uplinks.")
        status = str(port.get("status") or "").strip().lower()
        is_disabled = status in DISABLED_STATES
        if desired_state == "shutdown" and is_disabled:
            raise ChangeWorkflowError(409, "Port is already administratively disabled.")
        if desired_state == "no shutdown" and not is_disabled:
            raise ChangeWorkflowError(409, "Port is not administratively disabled.")

    @staticmethod
    def _matches_desired_state(port: dict[str, object], desired_state: str) -> bool:
        disabled = str(port.get("status") or "").strip().lower() in DISABLED_STATES
        return disabled if desired_state == "shutdown" else not disabled

    def _audit(self, proposal: LocalChangeProposal, *, status: str, **extra: object) -> None:
        record = {
            **asdict(proposal),
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "status": status,
            **extra,
        }
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_log_path.open("a", encoding="utf-8") as file_obj:
            file_obj.write(json.dumps(redact_value(record), ensure_ascii=False, sort_keys=True))
            file_obj.write("\n")
