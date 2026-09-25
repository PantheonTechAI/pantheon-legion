"""Runtime-owned admission record for one Centurion-led Mission investigation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
from uuid import UUID, uuid4

from legion_kernel.investigation import intent_digest


PROFILE = "READ_ONLY_CORPUS_V1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("INVESTIGATION_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


class InvestigationStatus(str, Enum):
    WAITING_CAPACITY = "WAITING_CAPACITY"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    CAPACITY_EXPIRED = "CAPACITY_EXPIRED"
    AUTHORITY_EXPIRED = "AUTHORITY_EXPIRED"


@dataclass(frozen=True)
class InvestigationIntake:
    intake_id: str
    command_id: str
    mission_id: str
    organization_id: str
    workspace_id: str
    profile: str
    intent_digest: str
    mission_version: int
    centurion_grant_id: str
    scout_grant_id: str
    expires_at: str
    deadline_at: str
    correlation_id: str
    requested_by: str
    status: InvestigationStatus
    version: int
    created_at: str
    updated_at: str
    last_error_code: str | None = None

    def __post_init__(self) -> None:
        for value in (self.intake_id, self.command_id, self.mission_id,
                      self.organization_id, self.workspace_id, self.correlation_id):
            UUID(value)
        if self.profile != PROFILE or not re.fullmatch(r"[0-9a-f]{64}", self.intent_digest):
            raise ValueError("INVALID_INVESTIGATION_INTENT")
        if self.mission_version < 1 or self.version < 1:
            raise ValueError("INVALID_INVESTIGATION_VERSION")
        if (not self.centurion_grant_id or not self.scout_grant_id
                or not self.requested_by):
            raise ValueError("INVALID_INVESTIGATION_AUTHORITY")
        for value in (self.expires_at, self.deadline_at, self.created_at, self.updated_at):
            _instant(value)
        if _instant(self.deadline_at) > _instant(self.expires_at):
            raise ValueError("INVALID_INVESTIGATION_DEADLINE")


class InvestigationAdmissionError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class RuntimeInvestigationAdmissions:
    """Trusted local intake port; subsequent work still needs fresh Aquila authority."""

    def __init__(self, repository, *, id_factory=lambda: str(uuid4()), clock=_now):
        self.repository = repository
        self.id_factory = id_factory
        self.clock = clock

    def admit(self, intent, mission) -> InvestigationIntake:
        # The local dispatcher supplies an Aquila outbox projection and a fresh
        # persisted Mission view. A replay is safe even after Mission cancellation.
        with self.repository.transaction(lock_key=f"investigation:{intent.mission_id}"):
            existing = self.repository.get_investigation_by_command(intent.command_id)
            if existing is not None:
                identity = (
                    "mission_id", "organization_id", "workspace_id", "profile",
                    "intent_digest", "mission_version", "centurion_grant_id",
                    "scout_grant_id", "expires_at", "correlation_id", "requested_by",
                )
                if any(getattr(existing, key) != getattr(intent, key) for key in identity):
                    raise InvestigationAdmissionError("INVESTIGATION_REPLAY_CONFLICT")
                return existing
            if mission is None or (mission.id != intent.mission_id
                    or mission.organization_id != intent.organization_id
                    or mission.workspace_id != intent.workspace_id):
                raise InvestigationAdmissionError("INVESTIGATION_SCOPE_MISMATCH")
            if mission.status.value != "ACTIVE":
                raise InvestigationAdmissionError(
                    "MISSION_NOT_ACTIVE" if mission.status.value in {
                        "PAUSED", "SUSPENDED", "AWAITING_APPROVAL",
                    } else "MISSION_TERMINAL"
                )
            expected = intent_digest(
                command_id=intent.command_id, mission_id=intent.mission_id,
                organization_id=intent.organization_id,
                workspace_id=intent.workspace_id, objective=mission.objective,
                profile=intent.profile,
            )
            if intent.profile != PROFILE or intent.intent_digest != expected:
                raise InvestigationAdmissionError("INVESTIGATION_INTENT_MISMATCH")
            if _instant(self.clock()) >= _instant(intent.expires_at):
                raise InvestigationAdmissionError("AUTHORITY_EXPIRED")
            if self.repository.get_investigation_by_mission(intent.mission_id) is not None:
                raise InvestigationAdmissionError("INVESTIGATION_ALREADY_ADMITTED")
            now = self.clock()
            intake = InvestigationIntake(
                intake_id=self.id_factory(), command_id=intent.command_id,
                mission_id=intent.mission_id,
                organization_id=intent.organization_id,
                workspace_id=intent.workspace_id, profile=intent.profile,
                intent_digest=intent.intent_digest,
                mission_version=intent.mission_version,
                centurion_grant_id=intent.centurion_grant_id,
                scout_grant_id=intent.scout_grant_id,
                expires_at=intent.expires_at,
                deadline_at=min(
                    (_instant(now) + timedelta(hours=2)),
                    _instant(intent.expires_at),
                ).isoformat().replace("+00:00", "Z"),
                correlation_id=intent.correlation_id,
                requested_by=intent.requested_by,
                status=InvestigationStatus.WAITING_CAPACITY,
                version=1, created_at=now, updated_at=now,
            )
            self.repository.save_investigation_intake(intake, expected_previous_version=None)
            return intake

    def reconcile_waiting(self, command_id: str) -> InvestigationIntake:
        initial = self.repository.get_investigation_by_command(command_id)
        if initial is None:
            raise InvestigationAdmissionError("INVESTIGATION_NOT_FOUND")
        with self.repository.transaction(lock_key=f"investigation:{initial.mission_id}"):
            intake = self.repository.get_investigation_by_command(command_id)
            if intake is None:
                raise InvestigationAdmissionError("INVESTIGATION_NOT_FOUND")
            if intake.status != InvestigationStatus.WAITING_CAPACITY:
                return intake
            now = self.clock()
            if _instant(now) < _instant(intake.deadline_at):
                return intake
            status = (InvestigationStatus.AUTHORITY_EXPIRED if _instant(now) >= _instant(intake.expires_at)
                      else InvestigationStatus.CAPACITY_EXPIRED)
            updated = replace(
                intake, status=status, version=intake.version + 1,
                updated_at=now, last_error_code=status.value,
            )
            self.repository.save_investigation_intake(
                updated, expected_previous_version=intake.version,
            )
            return updated
