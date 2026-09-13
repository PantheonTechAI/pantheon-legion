"""Small, provider-neutral Mission kernel used by the M1 acceptance tests.

This module deliberately has no HTTP, database, workflow, model, or cognition
runtime dependency. It is a reference for the invariants that Aquila and a
durable execution adapter must preserve.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Callable
from uuid import UUID, uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _expires_at(value: str, minutes: int = 15) -> str:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (instant + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


class PrincipalType(str, Enum):
    HUMAN = "HUMAN"
    WORKLOAD = "WORKLOAD"
    SYSTEM = "SYSTEM"
    EXTERNAL = "EXTERNAL"


class MissionStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class RoeLevel(str, Enum):
    OBSERVE = "OBSERVE"
    RECOMMEND = "RECOMMEND"
    REVIEW = "REVIEW"
    BOUNDED_AUTONOMOUS = "BOUNDED_AUTONOMOUS"


ROE_ORDER = {
    RoeLevel.OBSERVE: 0,
    RoeLevel.RECOMMEND: 1,
    RoeLevel.REVIEW: 2,
    RoeLevel.BOUNDED_AUTONOMOUS: 3,
}

COMMAND_TYPES = frozenset({
    "UPDATE_OBJECTIVE", "ADD_CONSTRAINT", "REMOVE_CONSTRAINT", "SET_ROE",
    "ADD_PARTICIPANT", "REMOVE_PARTICIPANT", "START", "PAUSE", "SUSPEND",
    "RESUME", "REQUEST_ACTION", "CANCEL", "COMPLETE",
})


@dataclass(frozen=True)
class Principal:
    type: PrincipalType
    subject: str
    roles: frozenset[str] = frozenset()

    def has_any_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


@dataclass
class Constraint:
    id: str
    text: str
    severity: str
    added_by: Principal
    added_at: str


@dataclass
class Participant:
    principal: Principal
    role: str
    scope: str | None = None


@dataclass
class RulesOfEngagement:
    revision: int
    level: RoeLevel
    changed_by: Principal
    effective_at: str
    approval_required_for: frozenset[str] = frozenset(
        {"MUTATION", "EXTERNAL_SIDE_EFFECT", "CREDENTIAL_USE", "PRODUCTION_ACCESS"}
    )
    allowed_capabilities: frozenset[str] = frozenset()
    denied_capabilities: frozenset[str] = frozenset()
    reason: str = ""


@dataclass
class Action:
    id: str
    command_id: str
    capability: str
    arguments: dict[str, Any]
    target: str | None
    side_effect_class: str
    requested_by: Principal
    requested_at: str


@dataclass
class Approval:
    id: str
    mission_id: str
    command_id: str
    action: Action
    mission_version: int
    roe_revision: int
    action_hash: str
    requested_by: Principal
    status: str = "PENDING"
    approver: Principal | None = None
    decision_reason: str | None = None
    decided_at: str | None = None
    expires_at: str | None = None
    consumed_at: str | None = None


@dataclass
class AuditEvent:
    id: str
    sequence: int
    mission_id: str
    mission_version: int
    event_type: str
    occurred_at: str
    actor: Principal
    result: str
    correlation_id: str
    command_id: str | None = None
    approval_id: str | None = None
    causation_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Mission:
    id: str
    organization_id: str
    workspace_id: str
    title: str
    objective: str
    created_by: Principal
    status: MissionStatus = MissionStatus.DRAFT
    version: int = 1
    roe: RulesOfEngagement | None = None
    constraints: list[Constraint] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    actions: dict[str, Action] = field(default_factory=dict)


@dataclass
class CommandResult:
    command_id: str
    status: str
    mission_id: str
    mission_version: int
    error_code: str | None = None
    message: str | None = None
    approval_id: str | None = None


class AuthorizationError(Exception):
    """Raised only for internal misuse; protocol denials return CommandResult."""


class WorkerKilled(RuntimeError):
    """Failure injection used to model a worker dying after a side effect."""


class LegionKernel:
    """In-memory reference implementation of the M1 Mission invariants."""

    def __init__(self, *, clock: Callable[[], str] = _now) -> None:
        self.clock = clock
        self.missions: dict[str, Mission] = {}
        self.approvals: dict[str, Approval] = {}
        self.audit: dict[str, list[AuditEvent]] = {}
        self.commands: dict[str, CommandResult] = {}
        self.idempotency: dict[tuple[str, str], tuple[str, CommandResult]] = {}
        self.side_effects: dict[str, int] = {}

    def create_mission(
        self,
        *,
        actor: Principal,
        organization_id: str,
        workspace_id: str,
        title: str,
        objective: str,
        roe_level: RoeLevel = RoeLevel.OBSERVE,
    ) -> Mission:
        if not actor.has_any_role("MISSION_OWNER", "OPERATOR"):
            raise AuthorizationError("MISSION_CREATE_FORBIDDEN")
        mission_id = str(uuid4())
        mission = Mission(
            id=mission_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
            title=title,
            objective=objective,
            created_by=actor,
            roe=RulesOfEngagement(
                revision=1,
                level=roe_level,
                changed_by=actor,
                effective_at=self.clock(),
            ),
        )
        self.missions[mission_id] = mission
        self.audit[mission_id] = []
        self._record(
            mission,
            event_type="MISSION_CREATED",
            actor=actor,
            result="SUCCESS",
            data={"status": mission.status.value},
        )
        return deepcopy(mission)

    def get_mission(self, mission_id: str) -> Mission:
        return deepcopy(self._mission(mission_id))

    def submit_command(
        self,
        *,
        mission_id: str,
        actor: Principal,
        expected_version: int,
        idempotency_key: str,
        command_type: str,
        payload: dict[str, Any],
        requested_by: Principal | None = None,
        correlation_id: str | None = None,
    ) -> CommandResult:
        mission = self._mission(mission_id)
        requested_by = requested_by or actor
        correlation_id = correlation_id or str(uuid4())
        fingerprint = self._fingerprint(
            command_type, payload, requested_by, actor, expected_version
        )
        idempotency_key_ref = (mission_id, idempotency_key)
        existing = self.idempotency.get(idempotency_key_ref)
        if existing:
            prior_fingerprint, prior_result = existing
            if prior_fingerprint != fingerprint:
                return self._reject(
                    mission,
                    actor,
                    "IDEMPOTENCY_KEY_REUSE",
                    "Idempotency key was used for a different command.",
                    correlation_id,
                )
            return deepcopy(prior_result)

        command_id = str(uuid4())
        if expected_version != mission.version:
            result = self._reject(
                mission,
                actor,
                "VERSION_CONFLICT",
                f"Mission version {mission.version} is current; command expected {expected_version}.",
                correlation_id,
                command_id=command_id,
            )
            self._remember(idempotency_key_ref, fingerprint, result)
            return result

        if command_type not in COMMAND_TYPES:
            result = self._reject(
                mission,
                actor,
                "UNKNOWN_COMMAND_TYPE",
                "Command type is not supported by this Mission protocol.",
                correlation_id,
                command_id=command_id,
            )
            self._remember(idempotency_key_ref, fingerprint, result)
            return result

        payload_error = self._payload_error(command_type, payload)
        if payload_error:
            result = self._reject(
                mission, actor, payload_error,
                "Command payload does not match the Mission protocol.", correlation_id,
                command_id=command_id,
            )
            self._remember(idempotency_key_ref, fingerprint, result)
            return result

        authorization_error = self._authorize_command(mission, actor, command_type)
        if authorization_error:
            result = self._reject(
                mission,
                actor,
                authorization_error,
                "Actor is not authorized for this command.",
                correlation_id,
                command_id=command_id,
            )
            self._remember(idempotency_key_ref, fingerprint, result)
            return result

        transition_error = self._validate_transition(mission, command_type)
        if transition_error:
            result = self._reject(
                mission,
                actor,
                transition_error,
                "Command is not valid for the current Mission state.",
                correlation_id,
                command_id=command_id,
            )
            self._remember(idempotency_key_ref, fingerprint, result)
            return result

        approval_id = None
        event_type = "COMMAND_ACCEPTED"
        if command_type == "UPDATE_OBJECTIVE":
            mission.objective = str(payload["objective"])
        elif command_type == "ADD_CONSTRAINT":
            raw = payload["constraint"]
            if raw["severity"] == "PROHIBITED" and any(
                c.severity == "REQUIRED" and c.text == raw["text"]
                for c in mission.constraints
            ):
                result = self._reject(
                    mission,
                    actor,
                    "CONSTRAINT_CONFLICT",
                    "Required and prohibited constraints conflict.",
                    correlation_id,
                    command_id=command_id,
                )
                self._remember(idempotency_key_ref, fingerprint, result)
                return result
            mission.constraints.append(
                Constraint(
                    id=str(raw["id"]),
                    text=str(raw["text"]),
                    severity=str(raw.get("severity", "REQUIRED")),
                    added_by=actor,
                    added_at=self.clock(),
                )
            )
        elif command_type == "REMOVE_CONSTRAINT":
            constraint_id = str(payload["constraint_id"])
            if not any(item.id == constraint_id for item in mission.constraints):
                result = self._reject(
                    mission,
                    actor,
                    "CONSTRAINT_NOT_FOUND",
                    "Constraint is not part of this Mission.",
                    correlation_id,
                    command_id=command_id,
                )
                self._remember(idempotency_key_ref, fingerprint, result)
                return result
            mission.constraints = [c for c in mission.constraints if c.id != constraint_id]
        elif command_type == "ADD_PARTICIPANT":
            participant = self._make_participant(payload)
            existing = next(
                (index for index, item in enumerate(mission.participants)
                 if item.principal.subject == participant.principal.subject),
                None,
            )
            if existing is None:
                mission.participants.append(participant)
                event_type = "PARTICIPANT_ADDED"
            else:
                mission.participants[existing] = participant
                event_type = "PARTICIPANT_UPDATED"
        elif command_type == "REMOVE_PARTICIPANT":
            subject = str(payload["subject"])
            if not any(item.principal.subject == subject for item in mission.participants):
                result = self._reject(
                    mission,
                    actor,
                    "PARTICIPANT_NOT_FOUND",
                    "Participant is not part of this Mission.",
                    correlation_id,
                    command_id=command_id,
                )
                self._remember(idempotency_key_ref, fingerprint, result)
                return result
            mission.participants = [
                item for item in mission.participants if item.principal.subject != subject
            ]
            event_type = "PARTICIPANT_REMOVED"
        elif command_type == "SET_ROE":
            requested_level = RoeLevel(payload["level"])
            mission.roe = RulesOfEngagement(
                revision=mission.roe.revision + 1,
                level=requested_level,
                changed_by=actor,
                effective_at=self.clock(),
                allowed_capabilities=frozenset(payload.get("allowed_capabilities", [])),
                denied_capabilities=frozenset(payload.get("denied_capabilities", [])),
                reason=str(payload["reason"]),
            )
            event_type = "ROE_CHANGED"
        elif command_type == "START":
            mission.status = MissionStatus.ACTIVE
        elif command_type == "PAUSE":
            mission.status = MissionStatus.PAUSED
        elif command_type == "SUSPEND":
            if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
                result = self._reject(
                    mission,
                    actor,
                    "SUSPENSION_REASON_REQUIRED",
                    "Suspending a Mission requires a reason.",
                    correlation_id,
                    command_id=command_id,
                )
                self._remember(idempotency_key_ref, fingerprint, result)
                return result
            mission.status = MissionStatus.SUSPENDED
        elif command_type == "RESUME":
            mission.status = MissionStatus.ACTIVE
        elif command_type == "CANCEL":
            mission.status = MissionStatus.CANCELLED
            for approval in self.approvals.values():
                if approval.mission_id == mission.id:
                    self._expire_approval_if_needed(
                        mission, approval, invalidation_reason="MISSION_CANCELLED"
                    )
        elif command_type == "COMPLETE":
            mission.status = MissionStatus.COMPLETED
        elif command_type == "REQUEST_ACTION":
            action = self._make_action(payload, requested_by, command_id)
            if self._capability_denied(mission.roe, action):
                result = self._reject(
                    mission,
                    actor,
                    "ROE_DENIED",
                    "Current Rules of Engagement deny this capability.",
                    correlation_id,
                    command_id=command_id,
                )
                self._remember(idempotency_key_ref, fingerprint, result)
                return result
            mission.actions[action.id] = action
            if self._requires_approval(mission.roe, action):
                mission.status = MissionStatus.AWAITING_APPROVAL
                approval_id = str(uuid4())
                approval = Approval(
                    id=approval_id,
                    mission_id=mission.id,
                    command_id=command_id,
                    action=action,
                    mission_version=mission.version + 1,
                    roe_revision=mission.roe.revision,
                    action_hash=self._action_hash(action),
                    requested_by=requested_by,
                    expires_at=_expires_at(self.clock()),
                )
                self.approvals[approval_id] = approval
                event_type = "APPROVAL_REQUESTED"

        mission.version += 1
        mission.updated_at = self.clock()
        event_data = {"command_type": command_type, "requested_by": requested_by.subject}
        if command_type == "SUSPEND":
            event_data["reason"] = payload["reason"].strip()
        if command_type == "ADD_PARTICIPANT":
            event_data["participant"] = {
                "subject": participant.principal.subject,
                "type": participant.principal.type.value,
                "role": participant.role,
                "scope": participant.scope,
            }
        if command_type == "REMOVE_PARTICIPANT":
            event_data["subject"] = subject
        self._record(
            mission,
            event_type=event_type,
            actor=actor,
            result="SUCCESS",
            command_id=command_id,
            correlation_id=correlation_id,
            data=event_data,
        )
        result = CommandResult(
            command_id=command_id,
            status="AWAITING_APPROVAL" if approval_id else "ACCEPTED",
            mission_id=mission.id,
            mission_version=mission.version,
            approval_id=approval_id,
        )
        self.commands[command_id] = deepcopy(result)
        self._remember(idempotency_key_ref, fingerprint, result)
        return deepcopy(result)

    def decide_approval(
        self,
        *,
        approval_id: str,
        approver: Principal,
        expected_mission_version: int,
        decision: str,
        reason: str,
    ) -> Approval:
        approval = self.approvals[approval_id]
        mission = self._mission(approval.mission_id)
        if not approver.has_any_role("APPROVER", "MISSION_OWNER"):
            raise AuthorizationError("FORBIDDEN")
        if self._expire_approval_if_needed(mission, approval):
            raise AuthorizationError("APPROVAL_STALE")
        if approval.status != "PENDING":
            raise AuthorizationError("APPROVAL_ALREADY_DECIDED")
        if expected_mission_version != mission.version or mission.version != approval.mission_version:
            raise AuthorizationError("APPROVAL_STALE")
        if decision not in {"APPROVE", "DENY", "REVOKE"}:
            raise ValueError("Unsupported approval decision")
        approval.status = {
            "APPROVE": "APPROVED",
            "DENY": "DENIED",
            "REVOKE": "REVOKED",
        }[decision]
        approval.approver = approver
        approval.decision_reason = reason
        approval.decided_at = self.clock()
        self._record(
            mission,
            event_type="APPROVAL_DECIDED",
            actor=approver,
            result="SUCCESS",
            approval_id=approval.id,
            data={"decision": decision, "reason": reason},
        )
        return deepcopy(approval)

    def execute_action(
        self,
        *,
        mission_id: str,
        action_id: str,
        worker: Principal,
        fail_after_side_effect: bool = False,
    ) -> str:
        mission = self._mission(mission_id)
        action = mission.actions[action_id]
        approval = self.validate_action_execution(
            mission_id=mission_id,
            action_id=action_id,
            worker=worker,
        )

        if self.side_effects.get(action_id):
            self._record(
                mission,
                event_type="EXECUTION_RETRIED",
                actor=worker,
                result="DUPLICATE",
                data={"action_id": action_id, "side_effect_count": self.side_effects[action_id]},
            )
            return "RECOVERED"

        if approval:
            approval.status = "CONSUMED"
            approval.consumed_at = self.clock()

        if mission.status == MissionStatus.AWAITING_APPROVAL:
            mission.status = MissionStatus.ACTIVE
            mission.version += 1
            mission.updated_at = self.clock()
        self.side_effects[action_id] = 1
        self._record(
            mission,
            event_type="EXECUTION_STARTED",
            actor=worker,
            result="SUCCESS",
            approval_id=approval.id if approval else None,
            data={"action_id": action_id, "side_effect_count": 1},
        )
        if fail_after_side_effect:
            raise WorkerKilled("worker killed after external side effect")
        self._record(
            mission,
            event_type="EXECUTION_COMPLETED",
            actor=worker,
            result="SUCCESS",
            approval_id=approval.id if approval else None,
            data={"action_id": action_id},
        )
        return "EXECUTED"

    def validate_action_execution(
        self,
        *,
        mission_id: str,
        action_id: str,
        worker: Principal,
    ) -> Approval | None:
        """Fail closed before a durable worker starts or resumes an action."""
        mission = self._mission(mission_id)
        action = mission.actions[action_id]
        error_code = self._execution_state_error(mission, worker)
        if error_code:
            self.reject_action_execution(
                mission_id=mission_id,
                action_id=action_id,
                worker=worker,
                error_code=error_code,
            )
            raise AuthorizationError(error_code)
        if self.side_effects.get(action_id):
            return None
        return self._approval_for_execution(mission, action, worker)

    def reject_action_execution(
        self,
        *,
        mission_id: str,
        action_id: str,
        worker: Principal,
        error_code: str,
    ) -> None:
        """Record a fail-closed execution-gate denial without changing Mission state."""
        mission = self._mission(mission_id)
        action = mission.actions[action_id]
        self._record(
            mission,
            event_type="EXECUTION_REJECTED",
            actor=worker,
            result="REJECTED",
            command_id=action.command_id,
            data={"action_id": action_id, "error_code": error_code},
        )

    def record_execution_authorization(
        self,
        *,
        mission_id: str,
        action_id: str,
        worker: Principal,
        decision_id: str,
        decision: str,
        reason: str,
        policy_version: str,
        evaluated_at: str,
    ) -> None:
        """Append the policy evaluation that preceded a durable action attempt."""
        mission = self._mission(mission_id)
        action = mission.actions[action_id]
        self._record(
            mission,
            event_type="AUTHORIZATION_EVALUATED",
            actor=worker,
            result=decision,
            command_id=action.command_id,
            data={
                "action_id": action_id,
                "decision_id": decision_id,
                "reason": reason,
                "policy_version": policy_version,
                "evaluated_at": evaluated_at,
                "operation": "EXECUTE_ACTION",
            },
        )

    def record_command_authorization(
        self,
        *,
        mission_id: str,
        actor: Principal,
        command_type: str,
        decision_id: str,
        decision: str,
        reason: str,
        policy_version: str,
        evaluated_at: str,
        correlation_id: str | None,
    ) -> None:
        """Append the policy evaluation that preceded a Mission command."""
        mission = self._mission(mission_id)
        self._record(
            mission,
            event_type="AUTHORIZATION_EVALUATED",
            actor=actor,
            result=decision,
            correlation_id=correlation_id,
            data={
                "command_type": command_type,
                "decision_id": decision_id,
                "reason": reason,
                "policy_version": policy_version,
                "evaluated_at": evaluated_at,
                "operation": "SUBMIT_COMMAND",
            },
        )

    def record_approval_authorization(
        self,
        *,
        mission_id: str,
        approval_id: str,
        actor: Principal,
        decision_id: str,
        decision: str,
        reason: str,
        policy_version: str,
        evaluated_at: str,
    ) -> None:
        """Append the policy evaluation that preceded an Approval decision."""
        mission = self._mission(mission_id)
        self._record(
            mission,
            event_type="AUTHORIZATION_EVALUATED",
            actor=actor,
            result=decision,
            approval_id=approval_id,
            data={
                "decision_id": decision_id,
                "reason": reason,
                "policy_version": policy_version,
                "evaluated_at": evaluated_at,
                "operation": "DECIDE_APPROVAL",
            },
        )

    def timeline(self, mission_id: str) -> list[AuditEvent]:
        return deepcopy(self.audit[mission_id])

    def audit_events(self, mission_id: str) -> list[AuditEvent]:
        return self.timeline(mission_id)

    def _mission(self, mission_id: str) -> Mission:
        try:
            return self.missions[mission_id]
        except KeyError as exc:
            raise KeyError(f"Unknown Mission {mission_id}") from exc

    @staticmethod
    def _make_participant(payload: dict[str, Any]) -> Participant:
        raw = payload["participant"]
        principal = raw["principal"]
        scope = raw.get("scope")
        if not isinstance(principal, dict) or not isinstance(principal.get("subject"), str):
            raise ValueError("participant principal must include a subject")
        if not principal["subject"]:
            raise ValueError("participant principal subject must not be empty")
        if scope is not None and not isinstance(scope, str):
            raise TypeError("participant scope must be a string")
        role = str(raw["role"])
        if role not in {"OWNER", "OPERATOR", "OBSERVER", "APPROVER", "WORKLOAD", "EXTERNAL"}:
            raise ValueError("Unsupported participant role")
        return Participant(
            principal=Principal(PrincipalType(principal["type"]), principal["subject"]),
            role=role,
            scope=scope,
        )

    @staticmethod
    def _payload_error(command_type: str, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return "INVALID_COMMAND_PAYLOAD"
        fields = {
            "UPDATE_OBJECTIVE": ({"objective"}, {"objective"}),
            "ADD_CONSTRAINT": ({"constraint"}, {"constraint"}),
            "REMOVE_CONSTRAINT": ({"constraint_id"}, {"constraint_id"}),
            "SET_ROE": ({"level", "reason"}, {"level", "reason", "allowed_capabilities", "denied_capabilities"}),
            "ADD_PARTICIPANT": ({"participant"}, {"participant"}),
            "REMOVE_PARTICIPANT": ({"subject"}, {"subject"}),
            "SUSPEND": ({"reason"}, {"reason"}),
            "REQUEST_ACTION": ({"action_id", "capability", "arguments"}, {"action_id", "capability", "arguments", "target", "side_effect_class"}),
        }
        required, allowed = fields.get(command_type, (set(), set()))
        if set(payload) - allowed:
            return "INVALID_COMMAND_PAYLOAD"
        if not required.issubset(payload):
            return "SUSPENSION_REASON_REQUIRED" if command_type == "SUSPEND" else "INVALID_COMMAND_PAYLOAD"
        if command_type == "SET_ROE" and not LegionKernel._valid_roe_payload(payload):
            return "INVALID_COMMAND_PAYLOAD"
        if command_type == "ADD_PARTICIPANT" and not LegionKernel._valid_participant_payload(payload):
            return "INVALID_COMMAND_PAYLOAD"
        if command_type == "REQUEST_ACTION" and not LegionKernel._valid_action_payload(payload):
            return "INVALID_COMMAND_PAYLOAD"
        return None

    @staticmethod
    def _valid_roe_payload(payload: dict[str, Any]) -> bool:
        if not isinstance(payload["level"], str) or payload["level"] not in {level.value for level in RoeLevel}:
            return False
        if not LegionKernel._bounded_string(payload["reason"], minimum=1, maximum=5000):
            return False
        return all(
            LegionKernel._valid_capability_list(payload.get(field))
            for field in ("allowed_capabilities", "denied_capabilities")
        )

    @staticmethod
    def _valid_participant_payload(payload: dict[str, Any]) -> bool:
        participant = payload["participant"]
        if not LegionKernel._object_has_only(
            participant, required={"principal", "role"}, allowed={"principal", "role", "scope"}
        ):
            return False
        principal = participant["principal"]
        if not LegionKernel._object_has_only(
            principal, required={"type", "subject"}, allowed={"type", "subject", "issuer"}
        ):
            return False
        if not isinstance(principal["type"], str) or principal["type"] not in {kind.value for kind in PrincipalType}:
            return False
        if not LegionKernel._bounded_string(principal["subject"], minimum=1, maximum=512):
            return False
        if "issuer" in principal and not LegionKernel._bounded_string(
            principal["issuer"], maximum=500
        ):
            return False
        if not isinstance(participant["role"], str) or participant["role"] not in {
            "OWNER", "OPERATOR", "OBSERVER", "APPROVER", "WORKLOAD", "EXTERNAL"
        }:
            return False
        return "scope" not in participant or LegionKernel._bounded_string(
            participant["scope"], maximum=2000
        )

    @staticmethod
    def _valid_action_payload(payload: dict[str, Any]) -> bool:
        if not LegionKernel._uuid_string(payload["action_id"]):
            return False
        if not LegionKernel._bounded_string(payload["capability"], minimum=1, maximum=200):
            return False
        if not isinstance(payload["arguments"], dict):
            return False
        if "target" in payload and not LegionKernel._bounded_string(payload["target"], maximum=1000):
            return False
        return "side_effect_class" not in payload or isinstance(payload["side_effect_class"], str) and payload["side_effect_class"] in {
            "READ", "ANALYSIS", "MUTATION", "EXTERNAL_SIDE_EFFECT"
        }

    @staticmethod
    def _valid_capability_list(value: Any) -> bool:
        if value is None:
            return True
        return (
            isinstance(value, list)
            and all(LegionKernel._bounded_string(item, minimum=1, maximum=200) for item in value)
            and len(value) == len(set(value))
        )

    @staticmethod
    def _object_has_only(value: Any, *, required: set[str], allowed: set[str]) -> bool:
        return (
            isinstance(value, dict)
            and required.issubset(value)
            and not (set(value) - allowed)
        )

    @staticmethod
    def _bounded_string(value: Any, *, minimum: int = 0, maximum: int) -> bool:
        return isinstance(value, str) and minimum <= len(value) <= maximum

    @staticmethod
    def _uuid_string(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            UUID(value)
        except ValueError:
            return False
        return True

    def _authorize_command(self, mission: Mission, actor: Principal, command_type: str) -> str | None:
        if actor.type == PrincipalType.HUMAN and actor.has_any_role("MISSION_OWNER", "OPERATOR"):
            return None
        if actor.type == PrincipalType.WORKLOAD and command_type == "REQUEST_ACTION" and actor.has_any_role("MISSION_WORKER"):
            return None
        return "FORBIDDEN"

    @staticmethod
    def _validate_transition(mission: Mission, command_type: str) -> str | None:
        if mission.status in {MissionStatus.COMPLETED, MissionStatus.CANCELLED}:
            return "MISSION_TERMINAL"
        allowed = {
            "START": {MissionStatus.DRAFT},
            "PAUSE": {MissionStatus.ACTIVE},
            "SUSPEND": {
                MissionStatus.ACTIVE,
                MissionStatus.PAUSED,
                MissionStatus.AWAITING_APPROVAL,
            },
            "RESUME": {MissionStatus.PAUSED, MissionStatus.SUSPENDED, MissionStatus.FAILED},
            "CANCEL": {
                MissionStatus.DRAFT,
                MissionStatus.ACTIVE,
                MissionStatus.PAUSED,
                MissionStatus.AWAITING_APPROVAL,
                MissionStatus.SUSPENDED,
                MissionStatus.FAILED,
            },
            "COMPLETE": {MissionStatus.ACTIVE},
            "REQUEST_ACTION": {MissionStatus.ACTIVE},
        }
        if command_type in allowed and mission.status not in allowed[command_type]:
            return "INVALID_STATE_TRANSITION"
        return None

    @staticmethod
    def _execution_state_error(mission: Mission, worker: Principal) -> str | None:
        if not worker.has_any_role("MISSION_WORKER", "OPERATOR"):
            return "FORBIDDEN"
        if mission.status in {
            MissionStatus.COMPLETED,
            MissionStatus.CANCELLED,
            MissionStatus.FAILED,
        }:
            return "MISSION_TERMINAL"
        if mission.status == MissionStatus.PAUSED:
            return "MISSION_PAUSED"
        if mission.status == MissionStatus.SUSPENDED:
            return "MISSION_SUSPENDED"
        return None

    def _approval_for_execution(
        self, mission: Mission, action: Action, worker: Principal
    ) -> Approval | None:
        approval = next(
            (item for item in self.approvals.values() if item.action.id == action.id), None
        )
        if approval:
            error_code = None
            if self._expire_approval_if_needed(mission, approval):
                error_code = "APPROVAL_STALE"
            elif approval.status != "APPROVED":
                error_code = "APPROVAL_STALE"
            elif mission.version != approval.mission_version:
                error_code = "APPROVAL_STALE"
            elif mission.roe.revision != approval.roe_revision:
                error_code = "ROE_DENIED"
            elif self._capability_denied(mission.roe, action):
                error_code = "ROE_DENIED"
            if error_code:
                self.reject_action_execution(
                    mission_id=mission.id,
                    action_id=action.id,
                    worker=worker,
                    error_code=error_code,
                )
                raise AuthorizationError(error_code)
        return approval

    def _expire_approval_if_needed(
        self,
        mission: Mission,
        approval: Approval,
        *,
        invalidation_reason: str | None = None,
    ) -> bool:
        if (
            invalidation_reason is None
            and (not approval.expires_at or self.clock() < approval.expires_at)
        ):
            return False
        if approval.status not in {"PENDING", "APPROVED"}:
            return approval.status == "EXPIRED"
        approval.status = "EXPIRED"
        self._record(
            mission,
            event_type="APPROVAL_EXPIRED",
            actor=Principal(PrincipalType.SYSTEM, "approval-expiry"),
            result="SUCCESS",
            approval_id=approval.id,
            data={
                "expires_at": approval.expires_at,
                "invalidation_reason": invalidation_reason or "EXPIRY",
            },
        )
        return True

    @staticmethod
    def _make_action(
        payload: dict[str, Any], requested_by: Principal, command_id: str
    ) -> Action:
        return Action(
            id=str(payload["action_id"]),
            command_id=command_id,
            capability=str(payload["capability"]),
            arguments=dict(payload.get("arguments", {})),
            target=payload.get("target"),
            side_effect_class=str(payload.get("side_effect_class", "READ")),
            requested_by=requested_by,
            requested_at=_now(),
        )

    @staticmethod
    def _action_hash(action: Action) -> str:
        value = json.dumps(
            {
                "id": action.id,
                "capability": action.capability,
                "arguments": action.arguments,
                "target": action.target,
                "side_effect_class": action.side_effect_class,
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def _capability_denied(roe: RulesOfEngagement, action: Action) -> bool:
        if action.capability in roe.denied_capabilities:
            return True
        return bool(roe.allowed_capabilities) and action.capability not in roe.allowed_capabilities

    @staticmethod
    def _requires_approval(roe: RulesOfEngagement, action: Action) -> bool:
        if action.side_effect_class in roe.approval_required_for:
            return True
        if action.side_effect_class == "READ":
            return False
        return ROE_ORDER[roe.level] < ROE_ORDER[RoeLevel.BOUNDED_AUTONOMOUS]

    def _record(
        self,
        mission: Mission,
        *,
        event_type: str,
        actor: Principal,
        result: str,
        correlation_id: str | None = None,
        command_id: str | None = None,
        approval_id: str | None = None,
        causation_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> AuditEvent:
        events = self.audit[mission.id]
        event = AuditEvent(
            id=str(uuid4()),
            sequence=len(events) + 1,
            mission_id=mission.id,
            mission_version=mission.version,
            event_type=event_type,
            occurred_at=self.clock(),
            actor=actor,
            result=result,
            correlation_id=correlation_id or str(uuid4()),
            command_id=command_id,
            approval_id=approval_id,
            causation_id=causation_id,
            data=data or {},
        )
        events.append(event)
        return event

    def _reject(
        self,
        mission: Mission,
        actor: Principal,
        error_code: str,
        message: str,
        correlation_id: str,
        *,
        command_id: str | None = None,
    ) -> CommandResult:
        self._record(
            mission,
            event_type="COMMAND_REJECTED",
            actor=actor,
            result="REJECTED",
            correlation_id=correlation_id,
            command_id=command_id,
            data={"error_code": error_code, "message": message},
        )
        result = CommandResult(
            command_id=command_id or str(uuid4()),
            status="REJECTED",
            mission_id=mission.id,
            mission_version=mission.version,
            error_code=error_code,
            message=message,
        )
        self.commands[result.command_id] = deepcopy(result)
        return result

    def _remember(
        self,
        key: tuple[str, str],
        fingerprint: str,
        result: CommandResult,
    ) -> None:
        self.idempotency[key] = (fingerprint, deepcopy(result))

    @staticmethod
    def _fingerprint(
        command_type: str,
        payload: dict[str, Any],
        requested_by: Principal,
        actor: Principal,
        expected_version: int,
    ) -> str:
        return json.dumps(
            {
                "command_type": command_type,
                "payload": payload,
                "requested_by": requested_by.subject,
                "actor": actor.subject,
                "expected_version": expected_version,
            },
            sort_keys=True,
        )
