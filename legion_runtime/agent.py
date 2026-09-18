"""Persistent organizational Agent domain types.

These records deliberately contain identity and coordination references only.
Models, prompts, credentials, processes, hosts, and framework state are runtime
resources and must not become Agent identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Any
from uuid import UUID


class AgentRole(str, Enum):
    SCOUT = "SCOUT"
    CENTURION = "CENTURION"


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"


class AssignmentStatus(str, Enum):
    PENDING_AUTHORIZATION = "PENDING_AUTHORIZATION"
    ASSIGNED = "ASSIGNED"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


class CheckpointState(str, Enum):
    WAITING_FOR_AUTHORITY = "WAITING_FOR_AUTHORITY"
    READY = "READY"
    BLOCKED = "BLOCKED"


class NextIntent(str, Enum):
    AUTHORIZE_ASSIGNMENT = "AUTHORIZE_ASSIGNMENT"
    ASSESS_MISSION = "ASSESS_MISSION"
    AWAIT_WORK_RESULT = "AWAIT_WORK_RESULT"
    ASSESS_WORK_RESULT = "ASSESS_WORK_RESULT"
    AWAIT_WORK = "AWAIT_WORK"
    EXECUTE_WORK = "EXECUTE_WORK"


class BindingStatus(str, Enum):
    PENDING_AUTHORITY = "PENDING_AUTHORITY"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    RELEASED = "RELEASED"


@dataclass(frozen=True)
class ActorRef:
    type: str
    subject: str

    def __post_init__(self) -> None:
        _bounded(self.type, "actor type", 1, 64)
        _bounded(self.subject, "actor subject", 1, 512)


@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    organization_id: str
    workspace_id: str
    display_name: str
    role: AgentRole
    status: AgentStatus
    version: int
    created_by: ActorRef
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        _uuid(self.agent_id, "agent_id")
        _uuid(self.organization_id, "organization_id")
        _uuid(self.workspace_id, "workspace_id")
        _bounded(self.display_name, "display_name", 1, 200)
        _positive(self.version, "version")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")


@dataclass(frozen=True)
class MissionAssignment:
    assignment_id: str
    agent_id: str
    mission_id: str
    status: AssignmentStatus
    mission_version: int | None
    authorization_decision_id: str | None
    policy_version: str | None
    requested_by: ActorRef
    correlation_id: str
    last_error_code: str | None
    version: int
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        _uuid(self.assignment_id, "assignment_id")
        _uuid(self.agent_id, "agent_id")
        _uuid(self.mission_id, "mission_id")
        _uuid(self.correlation_id, "correlation_id")
        _positive(self.version, "version")
        if self.mission_version is not None:
            _positive(self.mission_version, "mission_version")
        _optional_bounded(self.authorization_decision_id, "authorization_decision_id", 512)
        _optional_bounded(self.policy_version, "policy_version", 256)
        _optional_bounded(self.last_error_code, "last_error_code", 256)
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")


@dataclass(frozen=True)
class CoordinationCheckpoint:
    assignment_id: str
    revision: int
    state: CheckpointState
    next_intent: NextIntent
    last_observed_mission_version: int | None
    correlation_id: str
    last_error_code: str | None
    updated_at: str
    focus_work_item_id: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.assignment_id, "assignment_id")
        _uuid(self.correlation_id, "correlation_id")
        _positive(self.revision, "revision")
        if self.last_observed_mission_version is not None:
            _positive(self.last_observed_mission_version, "last_observed_mission_version")
        _optional_bounded(self.last_error_code, "last_error_code", 256)
        if self.focus_work_item_id is not None:
            _uuid(self.focus_work_item_id, "focus_work_item_id")
        _timestamp(self.updated_at, "updated_at")


def legal_checkpoint_intents(role: AgentRole) -> frozenset[NextIntent]:
    if role == AgentRole.CENTURION:
        return frozenset(
            {
                NextIntent.AUTHORIZE_ASSIGNMENT,
                NextIntent.ASSESS_MISSION,
                NextIntent.AWAIT_WORK_RESULT,
                NextIntent.ASSESS_WORK_RESULT,
            }
        )
    if role == AgentRole.SCOUT:
        return frozenset(
            {
                NextIntent.AUTHORIZE_ASSIGNMENT,
                NextIntent.AWAIT_WORK,
                NextIntent.EXECUTE_WORK,
            }
        )
    raise ValueError(f"unsupported Agent role: {role}")


def assigned_intent(role: AgentRole) -> NextIntent:
    if role == AgentRole.CENTURION:
        return NextIntent.ASSESS_MISSION
    if role == AgentRole.SCOUT:
        return NextIntent.AWAIT_WORK
    raise ValueError(f"unsupported Agent role: {role}")


@dataclass(frozen=True)
class AgentRuntimeBinding:
    binding_id: str
    agent_id: str
    assignment_id: str
    workload_subject: str
    grant_id: str | None
    status: BindingStatus
    version: int
    started_at: str
    ended_at: str | None
    correlation_id: str
    last_error_code: str | None

    def __post_init__(self) -> None:
        _uuid(self.binding_id, "binding_id")
        _uuid(self.agent_id, "agent_id")
        _uuid(self.assignment_id, "assignment_id")
        _bounded(self.workload_subject, "workload_subject", 1, 512)
        _optional_bounded(self.grant_id, "grant_id", 512)
        _positive(self.version, "version")
        _timestamp(self.started_at, "started_at")
        if self.ended_at is not None:
            _timestamp(self.ended_at, "ended_at")
        _uuid(self.correlation_id, "correlation_id")
        _optional_bounded(self.last_error_code, "last_error_code", 256)


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    sequence: int
    event_type: str
    occurred_at: str
    agent_id: str
    actor: ActorRef
    result: str
    correlation_id: str
    mission_id: str | None = None
    assignment_id: str | None = None
    binding_id: str | None = None
    causation_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _uuid(self.event_id, "event_id")
        _positive(self.sequence, "sequence")
        _bounded(self.event_type, "event_type", 1, 128)
        _timestamp(self.occurred_at, "occurred_at")
        _uuid(self.agent_id, "agent_id")
        _bounded(self.result, "result", 1, 64)
        _uuid(self.correlation_id, "correlation_id")
        for name, value in (
            ("mission_id", self.mission_id),
            ("assignment_id", self.assignment_id),
            ("binding_id", self.binding_id),
        ):
            if value is not None:
                _uuid(value, name)
        _optional_bounded(self.causation_id, "causation_id", 512)
        if not isinstance(self.data, dict):
            raise TypeError("event data must be an object")
        if not all(isinstance(key, str) for key in self.data):
            raise TypeError("event data keys must be strings")
        try:
            encoded = json.dumps(self.data, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise TypeError("event data must be JSON serializable") from exc
        if len(encoded.encode("utf-8")) > 8192:
            raise ValueError("event data must not exceed 8192 bytes")


def _uuid(value: str, name: str) -> None:
    try:
        UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{name} must be a UUID") from exc


def _positive(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _bounded(value: str, name: str, minimum: int, maximum: int) -> None:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f"{name} must contain {minimum}..{maximum} characters")


def _optional_bounded(value: str | None, name: str, maximum: int) -> None:
    if value is not None:
        _bounded(value, name, 1, maximum)


def _timestamp(value: str, name: str) -> None:
    _bounded(value, name, 1, 64)
    if not value.endswith("Z"):
        raise ValueError(f"{name} must be a UTC timestamp")
