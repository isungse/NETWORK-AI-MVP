from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from ..auth import Principal, require_distinct_approver
from ..models import CommandPlan, Device
from ..write_policy import AdminState, build_interface_admin_change_plan


@dataclass(frozen=True)
class ChangeProposal:
    proposal_id: str
    device_id: str
    interface: str
    desired_state: AdminState
    operator_id: str
    approver_id: str
    commands: tuple[str, ...]
    created_at: str
    status: str = "approved-not-executed"


def prepare_interface_admin_change(
    device: Device,
    *,
    interface: str,
    desired_state: AdminState,
    operator: Principal,
    approver: Principal,
) -> tuple[ChangeProposal, CommandPlan]:
    require_distinct_approver(operator, approver)
    plan = build_interface_admin_change_plan(
        device,
        interface=interface,
        desired_state=desired_state,
    )
    proposal = ChangeProposal(
        proposal_id=uuid4().hex,
        device_id=device.device_id,
        interface=interface,
        desired_state=desired_state,
        operator_id=operator.principal_id,
        approver_id=approver.principal_id,
        commands=plan.commands,
        created_at=_timestamp(),
    )
    return proposal, plan


def append_change_audit(path: str | Path, proposal: ChangeProposal) -> None:
    audit_path = Path(path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(asdict(proposal), ensure_ascii=False, sort_keys=True))
        file_obj.write("\n")


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
