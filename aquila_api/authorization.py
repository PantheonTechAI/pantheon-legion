"""Deterministic, provider-neutral Aquila authorization MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import uuid4

from legion_kernel import MissionStatus, Principal, PrincipalType, RoeLevel


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class DelegationGrant:
    grant_id: str
    issuer: Principal
    subject: Principal
    mission_id: str
    allowed_operations: frozenset[str]
    roe_ceiling: RoeLevel
    expires_at: str
    revoked: bool = False


@dataclass(frozen=True)
class AuthorizationRequest:
    principal: Principal
    mission_id: str
    operation: str
    roe_level: RoeLevel
    mission_status: MissionStatus
    side_effect_class: str = "READ"
    capability: str | None = None
    approval_present: bool = False
    delegation: DelegationGrant | None = None


@dataclass(frozen=True)
class AuthorizationDecision:
    decision_id: str
    decision: Decision
    reason: str
    policy_version: str
    evaluated_at: str
    principal: Principal
    operation: str


@dataclass(frozen=True)
class AuthorizationPolicy:
    version: str = "mvp-1"
    read_operations: frozenset[str] = frozenset(
        {"READ_MISSION", "READ_TIMELINE", "READ_ARTIFACT"}
    )
    approver_roles: frozenset[str] = frozenset({"APPROVER", "MISSION_OWNER"})
    operator_roles: frozenset[str] = frozenset({"MISSION_OWNER", "OPERATOR"})
    reader_roles: frozenset[str] = frozenset(
        {"MISSION_OWNER", "OPERATOR", "OBSERVER", "APPROVER", "MISSION_WORKER"}
    )


ROE_ORDER = {
    RoeLevel.OBSERVE: 0,
    RoeLevel.RECOMMEND: 1,
    RoeLevel.REVIEW: 2,
    RoeLevel.BOUNDED_AUTONOMOUS: 3,
}


class AuthorizationEngine:
    """Evaluate identity, delegation, lifecycle, capability, and ROE in order."""

    def __init__(
        self,
        policy: AuthorizationPolicy | None = None,
        *,
        clock: Callable[[], str] = _now,
    ) -> None:
        self.policy = policy or AuthorizationPolicy()
        self.clock = clock

    def decide(self, request: AuthorizationRequest) -> AuthorizationDecision:
        reason = self._evaluate(request)
        return AuthorizationDecision(
            decision_id=str(uuid4()),
            decision=Decision.ALLOW if reason is None else Decision.DENY,
            reason=reason or "AUTHORIZED",
            policy_version=self.policy.version,
            evaluated_at=self.clock(),
            principal=request.principal,
            operation=request.operation,
        )

    def _evaluate(self, request: AuthorizationRequest) -> str | None:
        principal = request.principal
        if not principal.subject:
            return "MISSING_SUBJECT"

        if principal.type == PrincipalType.WORKLOAD:
            grant = request.delegation
            if grant is None:
                return "DELEGATION_REQUIRED"
            if grant.subject.subject != principal.subject or grant.mission_id != request.mission_id:
                return "DELEGATION_SCOPE_MISMATCH"
            if grant.revoked:
                return "DELEGATION_REVOKED"
            if self.clock() >= grant.expires_at:
                return "DELEGATION_EXPIRED"
            if request.operation not in grant.allowed_operations:
                return "DELEGATED_OPERATION_DENIED"
            if ROE_ORDER[request.roe_level] > ROE_ORDER[grant.roe_ceiling]:
                return "DELEGATED_ROE_EXCEEDED"

        if request.operation in self.policy.read_operations:
            if principal.type == PrincipalType.WORKLOAD:
                return None
            if principal.type != PrincipalType.HUMAN:
                return "READ_ROLE_REQUIRED"
            if not principal.has_any_role(*self.policy.reader_roles):
                return "READ_ROLE_REQUIRED"
            return None

        if request.mission_status in {MissionStatus.CANCELLED, MissionStatus.COMPLETED}:
            return "MISSION_TERMINAL"

        if request.operation == "DECIDE_APPROVAL":
            if not principal.has_any_role(*self.policy.approver_roles):
                return "APPROVER_REQUIRED"
            return None

        if principal.type == PrincipalType.HUMAN and not principal.has_any_role(*self.policy.operator_roles):
            return "OPERATOR_ROLE_REQUIRED"

        if request.operation == "SET_ROE" and request.roe_level == RoeLevel.BOUNDED_AUTONOMOUS:
            if not principal.has_any_role("MISSION_OWNER"):
                return "OWNER_REQUIRED_FOR_AUTONOMY"

        if request.side_effect_class == "READ":
            return None
        if request.capability is None:
            return "CAPABILITY_REQUIRED"
        if request.roe_level in {RoeLevel.OBSERVE, RoeLevel.RECOMMEND}:
            return "ROE_DENIED"
        if request.roe_level == RoeLevel.REVIEW and not request.approval_present:
            return "APPROVAL_REQUIRED"
        return None
