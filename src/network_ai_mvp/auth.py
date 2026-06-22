from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["operator", "approver"]


class AuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class Principal:
    principal_id: str
    role: Role


def require_role(principal: Principal, role: Role) -> None:
    if principal.role != role:
        raise AuthorizationError(f"Principal {principal.principal_id} requires role {role}.")


def require_distinct_approver(operator: Principal, approver: Principal) -> None:
    require_role(operator, "operator")
    require_role(approver, "approver")
    if operator.principal_id == approver.principal_id:
        raise AuthorizationError("Operator and approver must be distinct principals.")
