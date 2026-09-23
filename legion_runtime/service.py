"""Application service for the first persistent Centurion.

The service persists organizational intent before consulting Aquila.  Aquila
remains authoritative for assignment and resume; unavailable authority always
leaves explicit, recoverable fail-closed state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Callable
from uuid import uuid4

from legion_kernel import Principal, PrincipalType

from .agent import (
    ActorRef,
    AgentIdentity,
    AgentRole,
    AgentRuntimeBinding,
    AgentStatus,
    AssignmentStatus,
    BindingStatus,
    CheckpointState,
    CoordinationCheckpoint,
    MissionAssignment,
    assigned_intent,
    legal_checkpoint_intents,
    NextIntent,
    RuntimeEvent,
)
from .authority import (
    AquilaAgentAuthority,
    AuthorityDenied,
    AuthorityUnavailable,
    MissionAuthorityView,
)
from .cognition import (
    AgentEvidence,
    AgentCognitionRequest,
    AgentMissionContext,
    CognitionRejected,
    CognitionUnavailable,
    ReadOnlyCognition,
)
from .evidence import EvidenceReadError, GroundedEvidenceReadRequest, GroundedEvidenceReader
from .mission_context import AquilaMissionContext, AuthorizedMissionContext
from .work import (
    AttemptStage,
    AttemptStatus,
    EvidenceSourceType,
    WorkAttempt,
    WorkEvidenceReference,
    WorkItem,
    WorkKind,
    WorkResult,
    WorkStatus,
    result_digest,
)
from .repository import AgentRepository, IdempotencyRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RuntimeOperationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ResumeResult:
    agent: AgentIdentity
    assignment: MissionAssignment
    checkpoint: CoordinationCheckpoint
    binding: AgentRuntimeBinding


class PersistentAgentRuntime:
    """Persist and recover one Centurion's bounded coordination intent."""

    def __init__(
        self,
        repository: AgentRepository,
        authority: AquilaAgentAuthority,
        *,
        clock: Callable[[], str] = _now,
        id_factory: Callable[[], str] = lambda: str(uuid4()),
        mission_context: AquilaMissionContext | None = None,
        cognition: ReadOnlyCognition | None = None,
        evidence_reader: GroundedEvidenceReader | None = None,
        cognition_invoker=None,
        experimental_driver=None,
    ) -> None:
        self.repository = repository
        self.authority = authority
        self.clock = clock
        self.id_factory = id_factory

        self.mission_context = mission_context
        self.cognition = cognition
        self.evidence_reader = evidence_reader
        self.cognition_invoker = cognition_invoker
        self.experimental_driver = experimental_driver

    def close(self) -> None:
        self.repository.close()

    def create_centurion(
        self,
        *,
        actor: Principal,
        organization_id: str,
        workspace_id: str,
        display_name: str,
        idempotency_key: str,
    ) -> AgentIdentity:
        self._idempotency_key(idempotency_key)
        actor_ref = self._actor(actor)
        fingerprint = self._fingerprint(
            actor=actor_ref,
            organization_id=organization_id,
            workspace_id=workspace_id,
            display_name=display_name,
        )
        scope = f"{organization_id}:{workspace_id}"
        with self.repository.transaction(
            lock_key=f"organization:{organization_id}:workspace:{workspace_id}"
        ):
            prior = self._prior(scope, "CREATE_CENTURION", idempotency_key, fingerprint)
            if prior is not None:
                agent = self.repository.get_agent(prior.resource_id)
                if agent is None:
                    raise RuntimeOperationError("IDEMPOTENCY_RESOURCE_MISSING")
                return agent
            now = self.clock()
            agent = AgentIdentity(
                agent_id=self.id_factory(),
                organization_id=organization_id,
                workspace_id=workspace_id,
                display_name=display_name,
                role=AgentRole.CENTURION,
                status=AgentStatus.ACTIVE,
                version=1,
                created_by=actor_ref,
                created_at=now,
                updated_at=now,
            )
            self.repository.save_agent(agent, expected_previous_version=None)
            self._event(
                event_type="AgentCreated",
                agent_id=agent.agent_id,
                actor=actor_ref,
                result="SUCCESS",
                correlation_id=self.id_factory(),
                data={"role": agent.role.value},
            )
            self._remember(
                scope,
                "CREATE_CENTURION",
                idempotency_key,
                fingerprint,
                "agent",
                agent.agent_id,
            )
            return agent

    def create_scout(
        self,
        *,
        actor: Principal,
        organization_id: str,
        workspace_id: str,
        display_name: str,
        idempotency_key: str,
    ) -> AgentIdentity:
        self._idempotency_key(idempotency_key)
        actor_ref = self._actor(actor)
        fingerprint = self._fingerprint(
            actor=actor_ref,
            organization_id=organization_id,
            workspace_id=workspace_id,
            display_name=display_name,
        )
        scope = f"{organization_id}:{workspace_id}"
        with self.repository.transaction(
            lock_key=f"organization:{organization_id}:workspace:{workspace_id}"
        ):
            prior = self._prior(scope, "CREATE_SCOUT", idempotency_key, fingerprint)
            if prior is not None:
                agent = self.repository.get_agent(prior.resource_id)
                if agent is None:
                    raise RuntimeOperationError("IDEMPOTENCY_RESOURCE_MISSING")
                return agent
            now = self.clock()
            agent = AgentIdentity(
                agent_id=self.id_factory(),
                organization_id=organization_id,
                workspace_id=workspace_id,
                display_name=display_name,
                role=AgentRole.SCOUT,
                status=AgentStatus.ACTIVE,
                version=1,
                created_by=actor_ref,
                created_at=now,
                updated_at=now,
            )
            self.repository.save_agent(agent, expected_previous_version=None)
            self._event(
                event_type="AgentCreated",
                agent_id=agent.agent_id,
                actor=actor_ref,
                result="SUCCESS",
                correlation_id=self.id_factory(),
                data={"role": agent.role.value},
            )
            self._remember(
                scope,
                "CREATE_SCOUT",
                idempotency_key,
                fingerprint,
                "agent",
                agent.agent_id,
            )
            return agent

    def request_assignment(
        self,
        *,
        actor: Principal,
        agent_id: str,
        mission_id: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> MissionAssignment:
        self._idempotency_key(idempotency_key)
        actor_ref = self._actor(actor)
        fingerprint = self._fingerprint(
            actor=actor_ref,
            agent_id=agent_id,
            mission_id=mission_id,
            correlation_id=correlation_id,
        )
        with self.repository.transaction(lock_key=f"agent:{agent_id}"):
            prior = self._prior(
                agent_id, "REQUEST_ASSIGNMENT", idempotency_key, fingerprint
            )
            if prior is not None:
                assignment = self.repository.get_assignment(prior.resource_id)
                if assignment is None:
                    raise RuntimeOperationError("IDEMPOTENCY_RESOURCE_MISSING")
                if assignment.status != AssignmentStatus.PENDING_AUTHORIZATION:
                    return assignment
            else:
                agent = self._require_agent(agent_id)
                if self.repository.get_active_assignment(agent_id) is not None:
                    raise RuntimeOperationError("ACTIVE_ASSIGNMENT_EXISTS")
                now = self.clock()
                assignment = MissionAssignment(
                    assignment_id=self.id_factory(),
                    agent_id=agent_id,
                    mission_id=mission_id,
                    status=AssignmentStatus.PENDING_AUTHORIZATION,
                    mission_version=None,
                    authorization_decision_id=None,
                    policy_version=None,
                    requested_by=actor_ref,
                    correlation_id=correlation_id,
                    last_error_code=None,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
                checkpoint = CoordinationCheckpoint(
                    assignment_id=assignment.assignment_id,
                    revision=1,
                    state=CheckpointState.WAITING_FOR_AUTHORITY,
                    next_intent=NextIntent.AUTHORIZE_ASSIGNMENT,
                    last_observed_mission_version=None,
                    correlation_id=correlation_id,
                    last_error_code=None,
                    updated_at=now,
                )
                self.repository.save_assignment(assignment, expected_previous_version=None)
                self.repository.save_checkpoint(checkpoint, expected_previous_revision=None)
                self._event(
                    event_type="AgentAssignmentRequested",
                    agent_id=agent.agent_id,
                    actor=actor_ref,
                    result="PENDING",
                    correlation_id=correlation_id,
                    mission_id=mission_id,
                    assignment_id=assignment.assignment_id,
                )
                self._remember(
                    agent_id,
                    "REQUEST_ASSIGNMENT",
                    idempotency_key,
                    fingerprint,
                    "assignment",
                    assignment.assignment_id,
                )
        return self._authorize_assignment(assignment.assignment_id, actor)

    def reconcile_assignment(
        self,
        *,
        assignment_id: str,
        actor: Principal,
        idempotency_key: str,
    ) -> MissionAssignment:
        self._idempotency_key(idempotency_key)
        actor_ref = self._actor(actor)
        fingerprint = self._fingerprint(actor=actor_ref, assignment_id=assignment_id)
        with self.repository.transaction(lock_key=f"assignment:{assignment_id}"):
            assignment = self._require_assignment(assignment_id)
            checkpoint = self._require_checkpoint(assignment_id)
            prior = self._prior(
                assignment_id, "RECONCILE_ASSIGNMENT", idempotency_key, fingerprint
            )
            if prior is not None:
                assignment = self._require_assignment(prior.resource_id)
                if assignment.status != AssignmentStatus.PENDING_AUTHORIZATION:
                    return assignment
            else:
                self._remember(
                    assignment_id,
                    "RECONCILE_ASSIGNMENT",
                    idempotency_key,
                    fingerprint,
                    "assignment",
                    assignment_id,
                )
            if assignment.status in {
                AssignmentStatus.ASSIGNED,
                AssignmentStatus.REJECTED,
            }:
                return assignment
            if checkpoint.next_intent != NextIntent.AUTHORIZE_ASSIGNMENT:
                raise RuntimeOperationError("RESUME_REQUIRED")
        return self._authorize_assignment(assignment_id, actor)

    def resume_assignment(
        self,
        *,
        assignment_id: str,
        workload: Principal,
        delegation_id: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> ResumeResult:
        self._idempotency_key(idempotency_key)
        if workload.type != PrincipalType.WORKLOAD:
            raise RuntimeOperationError("WORKLOAD_IDENTITY_REQUIRED")
        actor_ref = self._actor(workload)
        fingerprint = self._fingerprint(
            actor=actor_ref,
            assignment_id=assignment_id,
            delegation_id=delegation_id,
            correlation_id=correlation_id,
        )
        with self.repository.transaction(lock_key=f"assignment:{assignment_id}"):
            assignment = self._require_assignment(assignment_id)
            if assignment.status == AssignmentStatus.REJECTED:
                raise RuntimeOperationError("ASSIGNMENT_REJECTED")
            agent = self._require_agent(assignment.agent_id)
            checkpoint = self._require_checkpoint(assignment_id)
            if assignment.status not in {
                AssignmentStatus.ASSIGNED,
                AssignmentStatus.BLOCKED,
            } or (
                checkpoint.next_intent == NextIntent.AUTHORIZE_ASSIGNMENT
                or checkpoint.next_intent not in legal_checkpoint_intents(agent.role)
            ):
                raise RuntimeOperationError("ASSIGNMENT_NOT_AUTHORIZED")
            prior = self._prior(
                assignment_id, "RESUME_ASSIGNMENT", idempotency_key, fingerprint
            )
            if prior is not None:
                binding = self.repository.get_binding(prior.resource_id)
                if binding is None:
                    raise RuntimeOperationError("IDEMPOTENCY_RESOURCE_MISSING")
                if binding.status != BindingStatus.PENDING_AUTHORITY:
                    return ResumeResult(agent, assignment, checkpoint, binding)
            else:
                now = self.clock()
                binding = AgentRuntimeBinding(
                    binding_id=self.id_factory(),
                    agent_id=agent.agent_id,
                    assignment_id=assignment_id,
                    workload_subject=workload.subject,
                    grant_id=delegation_id,
                    status=BindingStatus.PENDING_AUTHORITY,
                    version=1,
                    started_at=now,
                    ended_at=None,
                    correlation_id=correlation_id,
                    last_error_code=None,
                )
                self.repository.save_binding(binding, expected_previous_version=None)
                self._remember(
                    assignment_id,
                    "RESUME_ASSIGNMENT",
                    idempotency_key,
                    fingerprint,
                    "binding",
                    binding.binding_id,
                )

        try:
            view = self.authority.authorize_resume(
                workload=workload,
                delegation_id=delegation_id,
                agent_id=agent.agent_id,
                assignment_id=assignment.assignment_id,
                mission_id=assignment.mission_id,
                binding_id=binding.binding_id,
                correlation_id=correlation_id,
            )
        except AuthorityUnavailable as exc:
            return self._block_resume(binding.binding_id, actor_ref, exc.code)
        except AuthorityDenied as exc:
            return self._block_resume(binding.binding_id, actor_ref, exc.code)

        if not self._scope_matches(agent, assignment, view):
            return self._block_resume(binding.binding_id, actor_ref, "SCOPE_MISMATCH")
        return self._activate_resume(binding.binding_id, actor_ref, view)

    def get_agent(self, agent_id: str) -> AgentIdentity | None:
        return self.repository.get_agent(agent_id)

    def get_assignment(self, assignment_id: str) -> MissionAssignment | None:
        return self.repository.get_assignment(assignment_id)

    def get_checkpoint(self, assignment_id: str) -> CoordinationCheckpoint | None:
        return self.repository.get_checkpoint(assignment_id)

    def list_bindings(self, assignment_id: str) -> list[AgentRuntimeBinding]:
        return self.repository.list_bindings(assignment_id)

    def list_events(self, agent_id: str) -> list[RuntimeEvent]:
        return self.repository.list_events(agent_id)


    def delegate_work(
        self,
        *,
        centurion_binding_id: str,
        workload: Principal,
        scout_assignment_id: str,
        objective: str,
        required_capabilities: tuple[str, ...],
        correlation_id: str,
        idempotency_key: str,
        causation_id: str | None = None,
        work_kind: WorkKind = WorkKind.READ_ONLY_ANALYSIS,
    ) -> WorkItem:
        self._idempotency_key(idempotency_key)
        expected_capabilities = {
            WorkKind.READ_ONLY_ANALYSIS: ("read_only_analysis",),
            WorkKind.TOOL_ASSISTED_CORPUS_ANALYSIS: ("read_only_analysis", "model_reasoning", "tabula_corpus_read"),
            WorkKind.COGNITION_INTEGRATION_SPIKE: ("experimental_cognition", "model_reasoning", "tabula_corpus_read", "fixture_effect"),
            WorkKind.GROUNDED_CORPUS_ANALYSIS: (
                "read_only_analysis",
                "tabula_corpus_read",
            ),
        }.get(work_kind)
        if work_kind == WorkKind.COGNITION_INTEGRATION_SPIKE and self.experimental_driver is None:
            raise RuntimeOperationError("EXPERIMENTAL_COGNITION_DISABLED")
        if expected_capabilities is None or required_capabilities != expected_capabilities:
            raise RuntimeOperationError("READ_ONLY_CAPABILITY_REQUIRED")
        if work_kind != WorkKind.READ_ONLY_ANALYSIS and len(objective) > 2000:
            raise RuntimeOperationError("GROUNDED_OBJECTIVE_TOO_LONG")
        binding = self._require_binding(centurion_binding_id)
        candidate_id = self.id_factory()
        now = self.clock()
        candidate = WorkItem(
            work_item_id=candidate_id,
            mission_id=self._require_assignment(binding.assignment_id).mission_id,
            centurion_agent_id=binding.agent_id,
            centurion_assignment_id=binding.assignment_id,
            scout_agent_id=self._require_assignment(scout_assignment_id).agent_id,
            scout_assignment_id=scout_assignment_id,
            objective=objective,
            required_capabilities=required_capabilities,
            status=WorkStatus.QUEUED,
            version=1,
            correlation_id=correlation_id,
            causation_id=causation_id,
            created_at=now,
            updated_at=now,
            kind=work_kind,
        )
        actor = self._actor(workload)
        fingerprint = self._fingerprint(
            actor=actor,
            centurion_binding_id=centurion_binding_id,
            scout_assignment_id=scout_assignment_id,
            objective=objective,
            required_capabilities=required_capabilities,
            correlation_id=correlation_id,
            causation_id=causation_id,
            work_kind=work_kind.value,
        )
        with self.repository.transaction(lock_keys=self._work_lock_keys(candidate)):
            centurion_binding, centurion_assignment, centurion = (
                self._require_active_actor(
                    centurion_binding_id,
                    workload,
                    AgentRole.CENTURION,
                )
            )
            scout_assignment = self._require_assignment(scout_assignment_id)
            scout = self._require_agent(scout_assignment.agent_id)
            if scout.role != AgentRole.SCOUT:
                raise RuntimeOperationError("SCOUT_ROLE_REQUIRED")
            if scout_assignment.status != AssignmentStatus.ASSIGNED:
                raise RuntimeOperationError("SCOUT_ASSIGNMENT_NOT_ACTIVE")
            if (
                centurion_assignment.mission_id != scout_assignment.mission_id
                or centurion_assignment.mission_id != candidate.mission_id
                or centurion.organization_id != scout.organization_id
                or centurion.workspace_id != scout.workspace_id
            ):
                raise RuntimeOperationError("WORK_SCOPE_MISMATCH")
            prior = self._prior(
                centurion_assignment.assignment_id,
                "DELEGATE_WORK",
                idempotency_key,
                fingerprint,
            )
            if prior is not None:
                existing = self.repository.get_work_item(prior.resource_id)
                if existing is None:
                    raise RuntimeOperationError("IDEMPOTENCY_RESOURCE_MISSING")
                return existing
            centurion_checkpoint = self._require_checkpoint(
                centurion_assignment.assignment_id
            )
            scout_checkpoint = self._require_checkpoint(scout_assignment_id)
            if centurion_checkpoint.focus_work_item_id is not None:
                raise RuntimeOperationError("CENTURION_WORK_ALREADY_FOCUSED")
            if scout_checkpoint.focus_work_item_id is not None:
                raise RuntimeOperationError("SCOUT_WORK_ALREADY_FOCUSED")
            self.repository.save_work_item(candidate, expected_previous_version=None)
            self.repository.save_checkpoint(
                replace(
                    centurion_checkpoint,
                    revision=centurion_checkpoint.revision + 1,
                    next_intent=NextIntent.AWAIT_WORK_RESULT,
                    focus_work_item_id=candidate.work_item_id,
                    correlation_id=correlation_id,
                    updated_at=now,
                ),
                expected_previous_revision=centurion_checkpoint.revision,
            )
            self.repository.save_checkpoint(
                replace(
                    scout_checkpoint,
                    revision=scout_checkpoint.revision + 1,
                    next_intent=NextIntent.EXECUTE_WORK,
                    focus_work_item_id=candidate.work_item_id,
                    correlation_id=correlation_id,
                    updated_at=now,
                ),
                expected_previous_revision=scout_checkpoint.revision,
            )
            event_data = {
                "work_item_id": candidate.work_item_id,
                "scout_agent_id": scout.agent_id,
                "required_capability_count": len(required_capabilities),
                "work_kind": work_kind.value,
            }
            self._event(
                event_type="ObjectiveDelegated",
                agent_id=centurion.agent_id,
                actor=actor,
                result="SUCCESS",
                correlation_id=correlation_id,
                mission_id=candidate.mission_id,
                assignment_id=centurion_assignment.assignment_id,
                binding_id=centurion_binding.binding_id,
                causation_id=causation_id,
                data=event_data,
            )
            self._event(
                event_type="WorkAssigned",
                agent_id=scout.agent_id,
                actor=actor,
                result="SUCCESS",
                correlation_id=correlation_id,
                mission_id=candidate.mission_id,
                assignment_id=scout_assignment.assignment_id,
                data={
                    "work_item_id": candidate.work_item_id,
                    "centurion_agent_id": centurion.agent_id,
                },
            )
            self._remember(
                centurion_assignment.assignment_id,
                "DELEGATE_WORK",
                idempotency_key,
                fingerprint,
                "work_item",
                candidate.work_item_id,
            )
            return candidate

    def claim_work(
        self,
        *,
        work_item_id: str,
        scout_binding_id: str,
        workload: Principal,
        idempotency_key: str,
    ) -> WorkAttempt:
        self._idempotency_key(idempotency_key)
        initial = self._require_work(work_item_id)
        actor = self._actor(workload)
        fingerprint = self._fingerprint(
            actor=actor,
            work_item_id=work_item_id,
            scout_binding_id=scout_binding_id,
        )
        with self.repository.transaction(lock_keys=self._work_lock_keys(initial)):
            work = self._require_work(work_item_id)
            binding, assignment, scout = self._require_active_actor(
                scout_binding_id,
                workload,
                AgentRole.SCOUT,
                assignment_id=work.scout_assignment_id,
            )
            prior = self._prior(
                work_item_id, "CLAIM_WORK", idempotency_key, fingerprint
            )
            if prior is not None:
                attempt = self.repository.get_work_attempt(prior.resource_id)
                if attempt is None:
                    raise RuntimeOperationError("IDEMPOTENCY_RESOURCE_MISSING")
                return attempt
            if work.status not in {WorkStatus.QUEUED, WorkStatus.RETRYABLE}:
                raise RuntimeOperationError("WORK_NOT_CLAIMABLE")
            attempts = self.repository.list_work_attempts(work_item_id)
            now = self.clock()
            attempt = WorkAttempt(
                attempt_id=self.id_factory(),
                work_item_id=work_item_id,
                scout_agent_id=scout.agent_id,
                scout_binding_id=binding.binding_id,
                status=AttemptStatus.PREPARED,
                attempt_number=len(attempts) + 1,
                mission_version=None,
                authorization_decision_id=None,
                error_code=None,
                version=1,
                created_at=now,
                updated_at=now,
            )
            self.repository.save_work_attempt(attempt, expected_previous_version=None)
            self.repository.save_work_item(
                replace(
                    work,
                    status=WorkStatus.CLAIMED,
                    version=work.version + 1,
                    updated_at=now,
                ),
                expected_previous_version=work.version,
            )
            self._event(
                event_type="WorkClaimed",
                agent_id=scout.agent_id,
                actor=actor,
                result="SUCCESS",
                correlation_id=work.correlation_id,
                mission_id=work.mission_id,
                assignment_id=assignment.assignment_id,
                binding_id=binding.binding_id,
                data={"work_item_id": work_item_id, "attempt_id": attempt.attempt_id},
            )
            self._remember(
                work_item_id,
                "CLAIM_WORK",
                idempotency_key,
                fingerprint,
                "work_attempt",
                attempt.attempt_id,
            )
            return attempt

    def execute_scout_work(
        self,
        *,
        work_item_id: str,
        scout_binding_id: str,
        workload: Principal,
        idempotency_key: str,
    ) -> WorkResult:
        self._idempotency_key(idempotency_key)
        if self.mission_context is None:
            raise RuntimeOperationError("MISSION_CONTEXT_UNAVAILABLE")
        initial = self._require_work(work_item_id)
        tool_assisted = initial.kind == WorkKind.TOOL_ASSISTED_CORPUS_ANALYSIS
        experimental = initial.kind == WorkKind.COGNITION_INTEGRATION_SPIKE
        if experimental and self.experimental_driver is None:
            raise RuntimeOperationError("EXPERIMENTAL_COGNITION_DISABLED")
        if not experimental and (self.cognition_invoker if tool_assisted else self.cognition) is None:
            raise RuntimeOperationError("COGNITION_UNAVAILABLE")
        if (
            initial.kind != WorkKind.READ_ONLY_ANALYSIS
            and self.evidence_reader is None
        ):
            raise RuntimeOperationError("GROUNDED_EVIDENCE_UNAVAILABLE")
        actor = self._actor(workload)
        fingerprint = self._fingerprint(
            actor=actor,
            work_item_id=work_item_id,
            scout_binding_id=scout_binding_id,
        )
        with self.repository.transaction(lock_keys=self._work_lock_keys(initial)):
            work = self._require_work(work_item_id)
            binding, assignment, scout = self._require_active_actor(
                scout_binding_id,
                workload,
                AgentRole.SCOUT,
                assignment_id=work.scout_assignment_id,
            )
            existing_result = self.repository.get_work_result(work_item_id)
            prior = self._prior(
                work_item_id, "EXECUTE_SCOUT_WORK", idempotency_key, fingerprint
            )
            if prior is not None and existing_result is not None:
                return existing_result
            if work.status != WorkStatus.CLAIMED:
                raise RuntimeOperationError("WORK_NOT_CLAIMED")
            attempt = self.repository.get_latest_work_attempt(work_item_id)
            if attempt is None or attempt.status != AttemptStatus.PREPARED:
                raise RuntimeOperationError("WORK_RECONCILIATION_REQUIRED")
            if prior is None:
                self._remember(
                    work_item_id,
                    "EXECUTE_SCOUT_WORK",
                    idempotency_key,
                    fingerprint,
                    "work_attempt",
                    attempt.attempt_id,
                )
            mission_stage = replace(
                attempt,
                status=AttemptStatus.RUNNING,
                attempt_stage=AttemptStage.MISSION_CONTEXT,
                version=attempt.version + 1,
                updated_at=self.clock(),
            )
            self.repository.save_work_attempt(
                mission_stage, expected_previous_version=attempt.version
            )

        attempt = mission_stage

        try:
            context = self.mission_context.authorize_and_read(
                workload=workload,
                delegation_id=binding.grant_id or "",
                agent_id=scout.agent_id,
                assignment_id=assignment.assignment_id,
                work_item_id=work_item_id,
                attempt_id=attempt.attempt_id,
                mission_id=work.mission_id,
                correlation_id=work.correlation_id,
            )
        except AuthorityUnavailable as exc:
            self._fail_work_attempt(work, attempt, actor, exc.code, retryable=True)
            raise RuntimeOperationError(exc.code) from exc
        except AuthorityDenied as exc:
            self._fail_work_attempt(work, attempt, actor, exc.code, retryable=False)
            raise RuntimeOperationError(exc.code) from exc

        if not self._work_context_matches(work, scout, context):
            self._fail_work_attempt(
                work, attempt, actor, "SCOPE_MISMATCH", retryable=False
            )
            raise RuntimeOperationError("SCOPE_MISMATCH")

        with self.repository.transaction(lock_keys=self._work_lock_keys(work)):
            current_work = self._require_work(work_item_id)
            current_attempt = self._require_work_attempt(attempt.attempt_id)
            binding, assignment, scout = self._require_active_actor(
                scout_binding_id,
                workload,
                AgentRole.SCOUT,
                assignment_id=current_work.scout_assignment_id,
            )
            if current_work.status == WorkStatus.CANCELLED:
                raise RuntimeOperationError("WORK_CANCELLED")
            if (
                current_work.status != WorkStatus.CLAIMED
                or current_attempt.status != AttemptStatus.RUNNING
                or current_attempt.attempt_stage != AttemptStage.MISSION_CONTEXT
            ):
                raise RuntimeOperationError("WORK_RECONCILIATION_REQUIRED")
            now = self.clock()
            running = replace(
                current_attempt,
                status=AttemptStatus.RUNNING,
                mission_version=context.mission_version,
                authorization_decision_id=context.authorization_decision_id,
                attempt_stage=(
                    AttemptStage.COGNITION_SELECTION if tool_assisted else
                    AttemptStage.EVIDENCE_RETRIEVAL
                    if current_work.kind == WorkKind.GROUNDED_CORPUS_ANALYSIS
                    else AttemptStage.COGNITION
                ),
                version=current_attempt.version + 1,
                updated_at=now,
            )
            self.repository.save_work_attempt(
                running, expected_previous_version=current_attempt.version
            )
            self._event(
                event_type="WorkAttemptStarted",
                agent_id=scout.agent_id,
                actor=actor,
                result="SUCCESS",
                correlation_id=current_work.correlation_id,
                mission_id=current_work.mission_id,
                assignment_id=assignment.assignment_id,
                binding_id=binding.binding_id,
                data={
                    "work_item_id": work_item_id,
                    "attempt_id": running.attempt_id,
                    "authorization_decision_id": context.authorization_decision_id,
                    "mission_version": context.mission_version,
                },
            )
            if current_work.kind == WorkKind.GROUNDED_CORPUS_ANALYSIS:
                self._event(
                    event_type="GroundedEvidenceRequested",
                    agent_id=scout.agent_id,
                    actor=actor,
                    result="STARTED",
                    correlation_id=current_work.correlation_id,
                    mission_id=current_work.mission_id,
                    assignment_id=assignment.assignment_id,
                    binding_id=binding.binding_id,
                    data={
                        "work_item_id": work_item_id,
                        "attempt_id": running.attempt_id,
                    },
                )

        cognition_evidence: tuple[AgentEvidence, ...] = ()
        tool_session = None
        evidence_query = work.objective
        if tool_assisted:
            from .tool_cognition import ToolCognitionSession
            tool_session = ToolCognitionSession(self, work, running, binding, assignment, scout, workload, context)
            evidence_query = tool_session.begin()
            running = tool_session.attempt
        if experimental:
            from .spike_session import SpikeAttemptSession
            tool_session = SpikeAttemptSession(self, work, running, binding, assignment, scout, workload, context)
            cognition_evidence = tool_session.run()
        if work.kind != WorkKind.READ_ONLY_ANALYSIS and not experimental:
            assert self.evidence_reader is not None
            try:
                if tool_session:
                    tool_session.guard()
                bundle = self.evidence_reader.read(
                    GroundedEvidenceReadRequest(
                        organization_id=scout.organization_id,
                        workspace_id=scout.workspace_id,
                        mission_id=work.mission_id,
                        agent_id=scout.agent_id,
                        assignment_id=assignment.assignment_id,
                        workload=workload,
                        delegation_id=binding.grant_id or "",
                        work_item_id=work_item_id,
                        attempt_id=running.attempt_id,
                        query=evidence_query,
                        correlation_id=work.correlation_id,
                    )
                )
            except RuntimeOperationError:
                raise
            except AuthorityUnavailable as exc:
                self._fail_work_attempt(work, running, actor, exc.code, retryable=True)
                raise RuntimeOperationError(exc.code) from exc
            except AuthorityDenied as exc:
                self._fail_work_attempt(work, running, actor, exc.code, retryable=False)
                raise RuntimeOperationError(exc.code) from exc
            except EvidenceReadError as exc:
                self._fail_work_attempt(
                    work, running, actor, exc.code, retryable=exc.retryable
                )
                raise RuntimeOperationError(exc.code) from exc
            except Exception as exc:
                self._fail_work_attempt(
                    work,
                    running,
                    actor,
                    "GROUNDED_EVIDENCE_UNAVAILABLE",
                    retryable=True,
                )
                raise RuntimeOperationError("GROUNDED_EVIDENCE_UNAVAILABLE") from exc

            references = tuple(
                WorkEvidenceReference(
                    evidence_reference_id=self.id_factory(),
                    work_item_id=work_item_id,
                    attempt_id=running.attempt_id,
                    source_type=EvidenceSourceType.TABULA_CORPUS,
                    external_record_id=item.record_id,
                    external_revision=item.revision,
                    canonical_uri=item.canonical_uri,
                    scope_binding_id=bundle.scope_binding_id,
                    scope_binding_version=bundle.scope_binding_version,
                    successful_authorization_decision_id=(
                        bundle.successful_authorization_decision_id
                    ),
                    tabula_audit_correlation_id=bundle.tabula_audit_correlation_id,
                    retrieved_at=item.retrieved_at,
                    created_at=self.clock(),
                )
                for item in bundle.records
            )
            with self.repository.transaction(lock_keys=self._work_lock_keys(work)):
                current_work = self._require_work(work_item_id)
                current_attempt = self._require_work_attempt(running.attempt_id)
                binding, assignment, scout = self._require_active_actor(
                    scout_binding_id,
                    workload,
                    AgentRole.SCOUT,
                    assignment_id=current_work.scout_assignment_id,
                )
                if current_work.status == WorkStatus.CANCELLED:
                    raise RuntimeOperationError("WORK_CANCELLED")
                if (
                    current_work.status != WorkStatus.CLAIMED
                    or current_attempt.status != AttemptStatus.RUNNING
                    or current_attempt.attempt_stage
                    != AttemptStage.EVIDENCE_RETRIEVAL
                ):
                    raise RuntimeOperationError("WORK_RECONCILIATION_REQUIRED")
                for reference in references:
                    self.repository.save_work_evidence_reference(reference)
                running = replace(
                    current_attempt,
                    attempt_stage=AttemptStage.COGNITION_CONTINUATION if tool_assisted else AttemptStage.COGNITION,
                    knowledge_authorization_decision_ids=(
                        bundle.authorization_decision_ids
                    ),
                    successful_knowledge_decision_id=(
                        bundle.successful_authorization_decision_id
                    ),
                    evidence_correlation_id=bundle.correlation_id,
                    tabula_audit_correlation_id=(
                        bundle.tabula_audit_correlation_id
                    ),
                    version=current_attempt.version + 1,
                    updated_at=self.clock(),
                )
                self.repository.save_work_attempt(
                    running, expected_previous_version=current_attempt.version
                )
                self._event(
                    event_type="GroundedEvidenceReferencesRecorded",
                    agent_id=scout.agent_id,
                    actor=actor,
                    result="SUCCESS",
                    correlation_id=current_work.correlation_id,
                    mission_id=current_work.mission_id,
                    assignment_id=assignment.assignment_id,
                    binding_id=binding.binding_id,
                    data={
                        "work_item_id": work_item_id,
                        "attempt_id": running.attempt_id,
                        "evidence_reference_ids": [
                            item.evidence_reference_id for item in references
                        ],
                        "evidence_count": len(references),
                        "authorization_decision_ids": list(
                            bundle.authorization_decision_ids
                        ),
                        "tabula_audit_correlation_id": (
                            bundle.tabula_audit_correlation_id
                        ),
                    },
                )
            cognition_evidence = tuple(
                AgentEvidence(
                    reference_id=reference.evidence_reference_id,
                    record_id=record.record_id,
                    revision=record.revision,
                    canonical_uri=record.canonical_uri,
                    content=record.content,
                    retrieved_at=record.retrieved_at,
                )
                for reference, record in zip(references, bundle.records, strict=True)
            )

        request = AgentCognitionRequest(
            request_id=running.attempt_id,
            agent_id=scout.agent_id,
            agent_role=scout.role,
            workload_subject=workload.subject,
            work_item_id=work_item_id,
            attempt_id=running.attempt_id,
            mission_id=work.mission_id,
            mission_version=context.mission_version,
            logical_capability=(
                "cognition_integration_spike" if experimental else
                "tool_assisted_corpus_analysis" if tool_assisted else "grounded_corpus_analysis"
                if work.kind == WorkKind.GROUNDED_CORPUS_ANALYSIS
                else "read_only_analysis"
            ),
            objective=work.objective,
            required_capabilities=work.required_capabilities,
            context=AgentMissionContext(
                mission_id=context.mission_id,
                mission_version=context.mission_version,
                status=context.mission_status,
                title=context.title,
                objective=context.objective,
                roe_level=context.roe_level,
                constraints=context.constraints,
            ),
            evidence=cognition_evidence,
        )
        try:
            cognition_result = tool_session.finish(request, running) if tool_session else self.cognition.run(request)
        except RuntimeOperationError:
            raise
        except CognitionRejected as exc:
            self._fail_work_attempt(work, running, actor, exc.code, retryable=False)
            raise RuntimeOperationError(exc.code) from exc
        except CognitionUnavailable as exc:
            self._fail_work_attempt(work, running, actor, exc.code, retryable=True)
            raise RuntimeOperationError(exc.code) from exc
        except Exception as exc:
            self._fail_work_attempt(
                work, running, actor, "COGNITION_UNAVAILABLE", retryable=True
            )
            raise RuntimeOperationError("COGNITION_UNAVAILABLE") from exc

        if not self._cognition_result_matches(request, cognition_result):
            self._fail_work_attempt(
                work,
                running,
                actor,
                "COGNITION_IDENTITY_MISMATCH",
                retryable=False,
            )
            raise RuntimeOperationError("COGNITION_IDENTITY_MISMATCH")
        if work.kind != WorkKind.READ_ONLY_ANALYSIS:
            allowed_references = {item.reference_id for item in cognition_evidence}
            cited_references = cognition_result.evidence_references
            if (
                not cited_references
                or len(cited_references) > 8
                or len(set(cited_references)) != len(cited_references)
                or not set(cited_references).issubset(allowed_references)
            ):
                self._fail_work_attempt(
                    work,
                    running,
                    actor,
                    "COGNITION_EVIDENCE_REFERENCES_INVALID",
                    retryable=False,
                )
                raise RuntimeOperationError(
                    "COGNITION_EVIDENCE_REFERENCES_INVALID"
                )
        try:
            result = WorkResult(
                result_id=self.id_factory(),
                work_item_id=work_item_id,
                attempt_id=running.attempt_id,
                scout_agent_id=scout.agent_id,
                scout_binding_id=binding.binding_id,
                mission_version=context.mission_version,
                summary=cognition_result.summary,
                evidence_references=cognition_result.evidence_references,
                content_digest=result_digest(
                    cognition_result.summary,
                    cognition_result.evidence_references,
                ),
                produced_at=self.clock(),
            )
        except (TypeError, ValueError) as exc:
            self._fail_work_attempt(
                work, running, actor, "COGNITION_RESULT_INVALID", retryable=False
            )
            raise RuntimeOperationError("COGNITION_RESULT_INVALID") from exc

        cancelled = False
        # The experimental fixture serializes its final authority check and
        # accepted-result commit with control mutations, in gate -> DB order.
        completion_gate = tool_session.completion_gate() if experimental else nullcontext()
        with completion_gate, self.repository.transaction(lock_keys=self._work_lock_keys(work)):
            current_work = self._require_work(work_item_id)
            current_attempt = self._require_work_attempt(running.attempt_id)
            existing = self.repository.get_work_result(work_item_id)
            if existing is not None:
                return existing
            now = self.clock()
            if current_work.status == WorkStatus.CANCELLED:
                if current_attempt.status == AttemptStatus.RUNNING:
                    self.repository.save_work_attempt(
                        replace(
                            current_attempt,
                            status=AttemptStatus.ABANDONED,
                            error_code="WORK_CANCELLED",
                            version=current_attempt.version + 1,
                            updated_at=now,
                        ),
                        expected_previous_version=current_attempt.version,
                    )
                cancelled = True
            else:
                if tool_session:
                    tool_session.guard()
                if (
                    current_work.status != WorkStatus.CLAIMED
                    or current_attempt.status != AttemptStatus.RUNNING
                ):
                    raise RuntimeOperationError("WORK_RECONCILIATION_REQUIRED")
                centurion_checkpoint = self._require_checkpoint(
                    current_work.centurion_assignment_id
                )
                scout_checkpoint = self._require_checkpoint(
                    current_work.scout_assignment_id
                )
                self.repository.save_work_result(result)
                self.repository.save_work_attempt(
                    replace(
                        current_attempt,
                        status=AttemptStatus.SUCCEEDED,
                        version=current_attempt.version + 1,
                        updated_at=now,
                    ),
                    expected_previous_version=current_attempt.version,
                )
                self.repository.save_work_item(
                    replace(
                        current_work,
                        status=WorkStatus.COMPLETED,
                        version=current_work.version + 1,
                        updated_at=now,
                    ),
                    expected_previous_version=current_work.version,
                )
                self.repository.save_checkpoint(
                    replace(
                        scout_checkpoint,
                        revision=scout_checkpoint.revision + 1,
                        next_intent=NextIntent.AWAIT_WORK,
                        focus_work_item_id=None,
                        updated_at=now,
                    ),
                    expected_previous_revision=scout_checkpoint.revision,
                )
                self.repository.save_checkpoint(
                    replace(
                        centurion_checkpoint,
                        revision=centurion_checkpoint.revision + 1,
                        next_intent=NextIntent.ASSESS_WORK_RESULT,
                        focus_work_item_id=work_item_id,
                        updated_at=now,
                    ),
                    expected_previous_revision=centurion_checkpoint.revision,
                )
                self._result_events(current_work, result, actor)
                if tool_session:
                    tool_session.event("GroundedCognitionCompleted", {"result_id": result.result_id,
                                       "supporting_evidence_count": len(result.evidence_references)})
        if cancelled:
            raise RuntimeOperationError("WORK_CANCELLED")
        return result

    def cancel_work(
        self,
        *,
        work_item_id: str,
        centurion_binding_id: str,
        workload: Principal,
        reason: str,
        idempotency_key: str,
    ) -> WorkItem:
        self._idempotency_key(idempotency_key)
        if not isinstance(reason, str) or not 1 <= len(reason.strip().encode("utf-8")) <= 1024:
            raise RuntimeOperationError("CANCELLATION_REASON_INVALID")
        initial = self._require_work(work_item_id)
        actor = self._actor(workload)
        fingerprint = self._fingerprint(
            actor=actor,
            work_item_id=work_item_id,
            centurion_binding_id=centurion_binding_id,
            reason=reason,
        )
        with self.repository.transaction(lock_keys=self._work_lock_keys(initial)):
            work = self._require_work(work_item_id)
            binding, assignment, centurion = self._require_active_actor(
                centurion_binding_id,
                workload,
                AgentRole.CENTURION,
                assignment_id=work.centurion_assignment_id,
            )
            prior = self._prior(
                work_item_id, "CANCEL_WORK", idempotency_key, fingerprint
            )
            if prior is not None:
                return self._require_work(prior.resource_id)
            if work.status in {
                WorkStatus.COMPLETED,
                WorkStatus.FAILED,
                WorkStatus.CANCELLED,
            }:
                raise RuntimeOperationError("WORK_TERMINAL")
            now = self.clock()
            cancelled = replace(
                work,
                status=WorkStatus.CANCELLED,
                version=work.version + 1,
                updated_at=now,
                cancelled_at=now,
                cancellation_reason=reason,
            )
            latest = self.repository.get_latest_work_attempt(work_item_id)
            if latest is not None and latest.status in {
                AttemptStatus.PREPARED,
                AttemptStatus.RUNNING,
            }:
                self.repository.save_work_attempt(
                    replace(
                        latest,
                        status=AttemptStatus.ABANDONED,
                        error_code="WORK_CANCELLED",
                        version=latest.version + 1,
                        updated_at=now,
                    ),
                    expected_previous_version=latest.version,
                )
            centurion_checkpoint = self._require_checkpoint(
                work.centurion_assignment_id
            )
            scout_checkpoint = self._require_checkpoint(work.scout_assignment_id)
            self.repository.save_work_item(
                cancelled, expected_previous_version=work.version
            )
            self.repository.save_checkpoint(
                replace(
                    centurion_checkpoint,
                    revision=centurion_checkpoint.revision + 1,
                    next_intent=NextIntent.ASSESS_MISSION,
                    focus_work_item_id=None,
                    updated_at=now,
                ),
                expected_previous_revision=centurion_checkpoint.revision,
            )
            self.repository.save_checkpoint(
                replace(
                    scout_checkpoint,
                    revision=scout_checkpoint.revision + 1,
                    next_intent=NextIntent.AWAIT_WORK,
                    focus_work_item_id=None,
                    updated_at=now,
                ),
                expected_previous_revision=scout_checkpoint.revision,
            )
            for agent_id, assignment_id in (
                (centurion.agent_id, assignment.assignment_id),
                (work.scout_agent_id, work.scout_assignment_id),
            ):
                self._event(
                    event_type="WorkCancelled",
                    agent_id=agent_id,
                    actor=actor,
                    result="SUCCESS",
                    correlation_id=work.correlation_id,
                    mission_id=work.mission_id,
                    assignment_id=assignment_id,
                    binding_id=(binding.binding_id if agent_id == centurion.agent_id else None),
                    data={"work_item_id": work_item_id},
                )
            self._remember(
                work_item_id,
                "CANCEL_WORK",
                idempotency_key,
                fingerprint,
                "work_item",
                work_item_id,
            )
            return cancelled

    def reconcile_work(
        self,
        *,
        work_item_id: str,
        scout_binding_id: str,
        workload: Principal,
        idempotency_key: str,
    ) -> WorkItem:
        self._idempotency_key(idempotency_key)
        initial = self._require_work(work_item_id)
        actor = self._actor(workload)
        fingerprint = self._fingerprint(
            actor=actor,
            work_item_id=work_item_id,
            scout_binding_id=scout_binding_id,
        )
        with self.repository.transaction(lock_keys=self._work_lock_keys(initial)):
            work = self._require_work(work_item_id)
            binding, assignment, scout = self._require_active_actor(
                scout_binding_id,
                workload,
                AgentRole.SCOUT,
                assignment_id=work.scout_assignment_id,
            )
            prior = self._prior(
                work_item_id, "RECONCILE_WORK", idempotency_key, fingerprint
            )
            if prior is not None:
                return self._require_work(prior.resource_id)
            if work.status in {
                WorkStatus.COMPLETED,
                WorkStatus.FAILED,
                WorkStatus.CANCELLED,
            }:
                reconciled = work
            else:
                attempt = self.repository.get_latest_work_attempt(work_item_id)
                if attempt is None or attempt.status == AttemptStatus.PREPARED:
                    reconciled = work
                elif attempt.status == AttemptStatus.RUNNING:
                    now = self.clock()
                    ambiguous_code = {
                        AttemptStage.MISSION_CONTEXT: "AMBIGUOUS_MISSION_CONTEXT_READ",
                        AttemptStage.EVIDENCE_RETRIEVAL: "AMBIGUOUS_EVIDENCE_RETRIEVAL",
                        AttemptStage.COGNITION: "AMBIGUOUS_COGNITION_OUTCOME",
                        AttemptStage.COGNITION_SELECTION: "AMBIGUOUS_COGNITION_SELECTION",
                        AttemptStage.COGNITION_INITIAL: "AMBIGUOUS_COGNITION_INVOCATION",
                        AttemptStage.TOOL_REQUESTED: "AMBIGUOUS_TOOL_REQUEST",
                        AttemptStage.COGNITION_CONTINUATION: "AMBIGUOUS_COGNITION_CONTINUATION",
                    }.get(attempt.attempt_stage, "AMBIGUOUS_COGNITION_OUTCOME")
                    self.repository.save_work_attempt(
                        replace(
                            attempt,
                            status=AttemptStatus.ABANDONED,
                            error_code=ambiguous_code,
                            version=attempt.version + 1,
                            updated_at=now,
                        ),
                        expected_previous_version=attempt.version,
                    )
                    reconciled = replace(
                        work,
                        status=WorkStatus.RETRYABLE,
                        version=work.version + 1,
                        updated_at=now,
                    )
                    self.repository.save_work_item(
                        reconciled, expected_previous_version=work.version
                    )
                    self._event(
                        event_type="WorkRecoveryBlocked",
                        agent_id=scout.agent_id,
                        actor=actor,
                        result="RETRYABLE",
                        correlation_id=work.correlation_id,
                        mission_id=work.mission_id,
                        assignment_id=assignment.assignment_id,
                        binding_id=binding.binding_id,
                        data={
                            "work_item_id": work_item_id,
                            "attempt_id": attempt.attempt_id,
                            "error_code": ambiguous_code,
                        },
                    )
                else:
                    reconciled = work
            self._remember(
                work_item_id,
                "RECONCILE_WORK",
                idempotency_key,
                fingerprint,
                "work_item",
                work_item_id,
            )
            return reconciled

    def get_work_item(self, work_item_id: str) -> WorkItem | None:
        return self.repository.get_work_item(work_item_id)

    def get_work_result(self, work_item_id: str) -> WorkResult | None:
        return self.repository.get_work_result(work_item_id)

    def list_work_for_assignment(self, assignment_id: str) -> list[WorkItem]:
        return self.repository.list_work_for_assignment(assignment_id)

    def list_work_for_mission(self, mission_id: str) -> list[WorkItem]:
        return self.repository.list_work_for_mission(mission_id)

    def list_work_evidence_references(
        self, *, work_item_id: str | None = None, attempt_id: str | None = None
    ) -> list[WorkEvidenceReference]:
        return self.repository.list_work_evidence_references(
            work_item_id=work_item_id, attempt_id=attempt_id
        )

    def _authorize_assignment(
        self, assignment_id: str, actor: Principal
    ) -> MissionAssignment:
        assignment = self._require_assignment(assignment_id)
        agent = self._require_agent(assignment.agent_id)
        try:
            view = self.authority.authorize_assignment(
                actor=actor,
                agent=agent,
                assignment_id=assignment.assignment_id,
                mission_id=assignment.mission_id,
                correlation_id=assignment.correlation_id,
            )
        except AuthorityUnavailable as exc:
            return self._complete_assignment(
                assignment_id, self._actor(actor), None, exc.code, unavailable=True
            )
        except AuthorityDenied as exc:
            return self._complete_assignment(
                assignment_id, self._actor(actor), None, exc.code, unavailable=False
            )
        if not self._scope_matches(agent, assignment, view):
            return self._complete_assignment(
                assignment_id,
                self._actor(actor),
                view,
                "SCOPE_MISMATCH",
                unavailable=False,
            )
        return self._complete_assignment(
            assignment_id, self._actor(actor), view, None, unavailable=False
        )

    def _complete_assignment(
        self,
        assignment_id: str,
        actor: ActorRef,
        view: MissionAuthorityView | None,
        error_code: str | None,
        *,
        unavailable: bool,
    ) -> MissionAssignment:
        with self.repository.transaction(lock_key=f"assignment:{assignment_id}"):
            current = self._require_assignment(assignment_id)
            checkpoint = self._require_checkpoint(assignment_id)
            agent = self._require_agent(current.agent_id)
            if current.status in {
                AssignmentStatus.ASSIGNED,
                AssignmentStatus.REJECTED,
            }:
                return current
            if error_code is None and view is not None:
                status = AssignmentStatus.ASSIGNED
                checkpoint_state = CheckpointState.READY
                next_intent = assigned_intent(agent.role)
                event_type = "AgentAssigned"
                result = "SUCCESS"
            elif unavailable:
                status = AssignmentStatus.BLOCKED
                checkpoint_state = CheckpointState.BLOCKED
                next_intent = NextIntent.AUTHORIZE_ASSIGNMENT
                event_type = "AgentRecoveryBlocked"
                result = "BLOCKED"
            else:
                status = AssignmentStatus.REJECTED
                checkpoint_state = CheckpointState.BLOCKED
                next_intent = NextIntent.AUTHORIZE_ASSIGNMENT
                event_type = "AgentAssignmentRejected"
                result = "DENY"
            if (
                current.status == status
                and current.last_error_code == error_code
                and checkpoint.state == checkpoint_state
                and checkpoint.last_error_code == error_code
            ):
                return current
            now = self.clock()
            updated = replace(
                current,
                status=status,
                mission_version=view.mission_version if view else current.mission_version,
                authorization_decision_id=(
                    view.decision_id if view else current.authorization_decision_id
                ),
                policy_version=view.policy_version if view else current.policy_version,
                last_error_code=error_code,
                version=current.version + 1,
                updated_at=now,
            )
            updated_checkpoint = replace(
                checkpoint,
                revision=checkpoint.revision + 1,
                state=checkpoint_state,
                next_intent=next_intent,
                last_observed_mission_version=(
                    view.mission_version
                    if view
                    else checkpoint.last_observed_mission_version
                ),
                last_error_code=error_code,
                updated_at=now,
            )
            self.repository.save_assignment(
                updated, expected_previous_version=current.version
            )
            self.repository.save_checkpoint(
                updated_checkpoint,
                expected_previous_revision=checkpoint.revision,
            )
            self._event(
                event_type=event_type,
                agent_id=current.agent_id,
                actor=actor,
                result=result,
                correlation_id=current.correlation_id,
                mission_id=current.mission_id,
                assignment_id=current.assignment_id,
                data={"error_code": error_code} if error_code else {},
            )
            return updated

    def _activate_resume(
        self,
        binding_id: str,
        actor: ActorRef,
        view: MissionAuthorityView,
    ) -> ResumeResult:
        pending_binding = self._require_binding(binding_id)
        with self.repository.transaction(
            lock_key=f"assignment:{pending_binding.assignment_id}"
        ):
            binding = self._require_binding(binding_id)
            assignment = self._require_assignment(binding.assignment_id)
            checkpoint = self._require_checkpoint(binding.assignment_id)
            agent = self._require_agent(binding.agent_id)
            if binding.status == BindingStatus.ACTIVE:
                return ResumeResult(agent, assignment, checkpoint, binding)
            if binding.status != BindingStatus.PENDING_AUTHORITY:
                return ResumeResult(agent, assignment, checkpoint, binding)
            now = self.clock()
            old_binding = self.repository.get_active_binding(binding.assignment_id)
            if old_binding is not None and old_binding.binding_id != binding.binding_id:
                released = replace(
                    old_binding,
                    status=BindingStatus.RELEASED,
                    version=old_binding.version + 1,
                    ended_at=now,
                    last_error_code=None,
                )
                self.repository.save_binding(
                    released, expected_previous_version=old_binding.version
                )
            active = replace(
                binding,
                status=BindingStatus.ACTIVE,
                version=binding.version + 1,
                last_error_code=None,
            )
            updated_assignment = replace(
                assignment,
                status=AssignmentStatus.ASSIGNED,
                mission_version=view.mission_version,
                authorization_decision_id=view.decision_id,
                policy_version=view.policy_version,
                last_error_code=None,
                version=assignment.version + 1,
                updated_at=now,
            )
            updated_checkpoint = replace(
                checkpoint,
                revision=checkpoint.revision + 1,
                state=CheckpointState.READY,
                last_observed_mission_version=view.mission_version,
                last_error_code=None,
                updated_at=now,
            )
            self.repository.save_binding(active, expected_previous_version=binding.version)
            self.repository.save_assignment(
                updated_assignment, expected_previous_version=assignment.version
            )
            self.repository.save_checkpoint(
                updated_checkpoint,
                expected_previous_revision=checkpoint.revision,
            )
            self._event(
                event_type="AgentRuntimeBound",
                agent_id=agent.agent_id,
                actor=actor,
                result="SUCCESS",
                correlation_id=binding.correlation_id,
                mission_id=assignment.mission_id,
                assignment_id=assignment.assignment_id,
                binding_id=binding.binding_id,
                data={"workload_subject": binding.workload_subject},
            )
            self._event(
                event_type="AgentResumed",
                agent_id=agent.agent_id,
                actor=actor,
                result="SUCCESS",
                correlation_id=binding.correlation_id,
                mission_id=assignment.mission_id,
                assignment_id=assignment.assignment_id,
                binding_id=binding.binding_id,
                data={"next_intent": updated_checkpoint.next_intent.value},
            )
            return ResumeResult(
                agent, updated_assignment, updated_checkpoint, active
            )

    def _block_resume(
        self, binding_id: str, actor: ActorRef, error_code: str
    ) -> ResumeResult:
        pending_binding = self._require_binding(binding_id)
        with self.repository.transaction(
            lock_key=f"assignment:{pending_binding.assignment_id}"
        ):
            binding = self._require_binding(binding_id)
            assignment = self._require_assignment(binding.assignment_id)
            checkpoint = self._require_checkpoint(binding.assignment_id)
            agent = self._require_agent(binding.agent_id)
            if binding.status != BindingStatus.PENDING_AUTHORITY:
                return ResumeResult(agent, assignment, checkpoint, binding)
            now = self.clock()
            blocked_binding = replace(
                binding,
                status=BindingStatus.BLOCKED,
                version=binding.version + 1,
                last_error_code=error_code,
            )
            blocked_assignment = replace(
                assignment,
                status=AssignmentStatus.BLOCKED,
                last_error_code=error_code,
                version=assignment.version + 1,
                updated_at=now,
            )
            blocked_checkpoint = replace(
                checkpoint,
                revision=checkpoint.revision + 1,
                state=CheckpointState.BLOCKED,
                last_error_code=error_code,
                updated_at=now,
            )
            self.repository.save_binding(
                blocked_binding, expected_previous_version=binding.version
            )
            self.repository.save_assignment(
                blocked_assignment, expected_previous_version=assignment.version
            )
            self.repository.save_checkpoint(
                blocked_checkpoint,
                expected_previous_revision=checkpoint.revision,
            )
            self._event(
                event_type="AgentRecoveryBlocked",
                agent_id=agent.agent_id,
                actor=actor,
                result="BLOCKED",
                correlation_id=binding.correlation_id,
                mission_id=assignment.mission_id,
                assignment_id=assignment.assignment_id,
                binding_id=binding.binding_id,
                data={"error_code": error_code},
            )
            return ResumeResult(
                agent, blocked_assignment, blocked_checkpoint, blocked_binding
            )

    @staticmethod
    def _work_lock_keys(work: WorkItem) -> tuple[str, ...]:
        return (
            f"work-item:{work.work_item_id}",
            f"assignment:{work.centurion_assignment_id}",
            f"assignment:{work.scout_assignment_id}",
        )

    def _require_active_actor(
        self,
        binding_id: str,
        workload: Principal,
        role: AgentRole,
        *,
        assignment_id: str | None = None,
    ) -> tuple[AgentRuntimeBinding, MissionAssignment, AgentIdentity]:
        if workload.type != PrincipalType.WORKLOAD:
            raise RuntimeOperationError("WORKLOAD_IDENTITY_REQUIRED")
        binding = self._require_binding(binding_id)
        if binding.status != BindingStatus.ACTIVE:
            raise RuntimeOperationError("ACTIVE_BINDING_REQUIRED")
        if binding.workload_subject != workload.subject:
            raise RuntimeOperationError("WORKLOAD_BINDING_MISMATCH")
        if assignment_id is not None and binding.assignment_id != assignment_id:
            raise RuntimeOperationError("WORKLOAD_BINDING_MISMATCH")
        assignment = self._require_assignment(binding.assignment_id)
        if assignment.status != AssignmentStatus.ASSIGNED:
            raise RuntimeOperationError("ASSIGNMENT_NOT_ACTIVE")
        agent = self._require_agent(binding.agent_id)
        if assignment.agent_id != agent.agent_id or agent.role != role:
            raise RuntimeOperationError("AGENT_ROLE_MISMATCH")
        return binding, assignment, agent

    @staticmethod
    def _work_context_matches(
        work: WorkItem,
        scout: AgentIdentity,
        context: AuthorizedMissionContext,
    ) -> bool:
        return (
            context.mission_id == work.mission_id
            and context.organization_id == scout.organization_id
            and context.workspace_id == scout.workspace_id
            and context.mission_status not in {"CANCELLED", "COMPLETED"}
        )

    @staticmethod
    def _cognition_result_matches(request, result) -> bool:
        return (
            result.request_id == request.request_id
            and result.agent_id == request.agent_id
            and result.work_item_id == request.work_item_id
            and result.attempt_id == request.attempt_id
            and result.mission_id == request.mission_id
            and result.mission_version == request.mission_version
        )

    def _fail_work_attempt(
        self,
        work: WorkItem,
        attempt: WorkAttempt,
        actor: ActorRef,
        error_code: str,
        *,
        retryable: bool,
    ) -> None:
        with self.repository.transaction(lock_keys=self._work_lock_keys(work)):
            current_work = self._require_work(work.work_item_id)
            current_attempt = self._require_work_attempt(attempt.attempt_id)
            if current_attempt.status in {
                AttemptStatus.SUCCEEDED,
                AttemptStatus.FAILED,
                AttemptStatus.ABANDONED,
            }:
                return
            now = self.clock()
            if current_work.status == WorkStatus.CANCELLED:
                self.repository.save_work_attempt(
                    replace(
                        current_attempt,
                        status=AttemptStatus.ABANDONED,
                        error_code="WORK_CANCELLED",
                        version=current_attempt.version + 1,
                        updated_at=now,
                    ),
                    expected_previous_version=current_attempt.version,
                )
                return
            next_status = WorkStatus.RETRYABLE if retryable else WorkStatus.FAILED
            self.repository.save_work_attempt(
                replace(
                    current_attempt,
                    status=AttemptStatus.FAILED,
                    error_code=error_code,
                    version=current_attempt.version + 1,
                    updated_at=now,
                ),
                expected_previous_version=current_attempt.version,
            )
            self.repository.save_work_item(
                replace(
                    current_work,
                    status=next_status,
                    version=current_work.version + 1,
                    updated_at=now,
                ),
                expected_previous_version=current_work.version,
            )
            scout_checkpoint = self._require_checkpoint(
                current_work.scout_assignment_id
            )
            self.repository.save_checkpoint(
                replace(
                    scout_checkpoint,
                    revision=scout_checkpoint.revision + 1,
                    next_intent=(
                        NextIntent.EXECUTE_WORK
                        if retryable
                        else NextIntent.AWAIT_WORK
                    ),
                    focus_work_item_id=(current_work.work_item_id if retryable else None),
                    last_error_code=error_code,
                    updated_at=now,
                ),
                expected_previous_revision=scout_checkpoint.revision,
            )
            if not retryable:
                centurion_checkpoint = self._require_checkpoint(
                    current_work.centurion_assignment_id
                )
                self.repository.save_checkpoint(
                    replace(
                        centurion_checkpoint,
                        revision=centurion_checkpoint.revision + 1,
                        next_intent=NextIntent.ASSESS_MISSION,
                        focus_work_item_id=None,
                        last_error_code=error_code,
                        updated_at=now,
                    ),
                    expected_previous_revision=centurion_checkpoint.revision,
                )
            self._event(
                event_type="WorkAttemptFailed",
                agent_id=current_work.scout_agent_id,
                actor=actor,
                result="RETRYABLE" if retryable else "FAILED",
                correlation_id=current_work.correlation_id,
                mission_id=current_work.mission_id,
                assignment_id=current_work.scout_assignment_id,
                binding_id=current_attempt.scout_binding_id,
                data={
                    "work_item_id": current_work.work_item_id,
                    "attempt_id": current_attempt.attempt_id,
                    "error_code": error_code,
                },
            )
            if (
                current_work.kind == WorkKind.GROUNDED_CORPUS_ANALYSIS
                and current_attempt.attempt_stage == AttemptStage.EVIDENCE_RETRIEVAL
            ):
                self._event(
                    event_type="GroundedEvidenceFailed",
                    agent_id=current_work.scout_agent_id,
                    actor=actor,
                    result="RETRYABLE" if retryable else "FAILED",
                    correlation_id=current_work.correlation_id,
                    mission_id=current_work.mission_id,
                    assignment_id=current_work.scout_assignment_id,
                    binding_id=current_attempt.scout_binding_id,
                    data={
                        "work_item_id": current_work.work_item_id,
                        "attempt_id": current_attempt.attempt_id,
                        "error_code": error_code,
                    },
                )

    def _result_events(
        self, work: WorkItem, result: WorkResult, actor: ActorRef
    ) -> None:
        common = {
            "work_item_id": work.work_item_id,
            "attempt_id": result.attempt_id,
            "result_id": result.result_id,
            "content_digest": result.content_digest,
            "evidence_reference_count": len(result.evidence_references),
        }
        self._event(
            event_type="WorkResultAvailable",
            agent_id=work.centurion_agent_id,
            actor=actor,
            result="SUCCESS",
            correlation_id=work.correlation_id,
            mission_id=work.mission_id,
            assignment_id=work.centurion_assignment_id,
            data=common,
        )
        self._event(
            event_type="WorkResultAccepted",
            agent_id=work.scout_agent_id,
            actor=actor,
            result="SUCCESS",
            correlation_id=work.correlation_id,
            mission_id=work.mission_id,
            assignment_id=work.scout_assignment_id,
            binding_id=result.scout_binding_id,
            data=common,
        )

    @staticmethod
    def _scope_matches(
        agent: AgentIdentity,
        assignment: MissionAssignment,
        view: MissionAuthorityView,
    ) -> bool:
        return (
            assignment.mission_id == view.mission_id
            and agent.organization_id == view.organization_id
            and agent.workspace_id == view.workspace_id
        )

    def _event(
        self,
        *,
        event_type: str,
        agent_id: str,
        actor: ActorRef,
        result: str,
        correlation_id: str,
        mission_id: str | None = None,
        assignment_id: str | None = None,
        binding_id: str | None = None,
        data: dict[str, Any] | None = None,
        causation_id: str | None = None,
    ) -> None:
        self.repository.append_event(
            RuntimeEvent(
                event_id=self.id_factory(),
                sequence=self.repository.next_event_sequence(agent_id),
                event_type=event_type,
                occurred_at=self.clock(),
                agent_id=agent_id,
                actor=actor,
                result=result,
                correlation_id=correlation_id,
                mission_id=mission_id,
                assignment_id=assignment_id,
                binding_id=binding_id,
                causation_id=causation_id,
                data=data or {},
            )
        )

    def _prior(
        self,
        scope: str,
        operation: str,
        key: str,
        fingerprint: str,
    ) -> IdempotencyRecord | None:
        prior = self.repository.get_idempotency(
            scope=scope, operation=operation, idempotency_key=key
        )
        if prior is not None and prior.fingerprint != fingerprint:
            raise RuntimeOperationError("IDEMPOTENCY_KEY_REUSE")
        return prior

    def _remember(
        self,
        scope: str,
        operation: str,
        key: str,
        fingerprint: str,
        resource_type: str,
        resource_id: str,
    ) -> None:
        self.repository.put_idempotency(
            IdempotencyRecord(
                scope=scope,
                operation=operation,
                idempotency_key=key,
                fingerprint=fingerprint,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        )

    @staticmethod
    def _fingerprint(**values: Any) -> str:
        normalized = {
            key: ({"type": value.type, "subject": value.subject} if isinstance(value, ActorRef) else value)
            for key, value in values.items()
        }
        payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _actor(principal: Principal) -> ActorRef:
        return ActorRef(principal.type.value, principal.subject)

    @staticmethod
    def _idempotency_key(value: str) -> None:
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 256:
            raise RuntimeOperationError("IDEMPOTENCY_KEY_REQUIRED")

    def _require_agent(self, agent_id: str) -> AgentIdentity:
        agent = self.repository.get_agent(agent_id)
        if agent is None:
            raise RuntimeOperationError("AGENT_NOT_FOUND")
        return agent

    def _require_assignment(self, assignment_id: str) -> MissionAssignment:
        assignment = self.repository.get_assignment(assignment_id)
        if assignment is None:
            raise RuntimeOperationError("ASSIGNMENT_NOT_FOUND")
        return assignment

    def _require_checkpoint(self, assignment_id: str) -> CoordinationCheckpoint:
        checkpoint = self.repository.get_checkpoint(assignment_id)
        if checkpoint is None:
            raise RuntimeOperationError("CHECKPOINT_NOT_FOUND")
        return checkpoint

    def _require_binding(self, binding_id: str) -> AgentRuntimeBinding:
        binding = self.repository.get_binding(binding_id)
        if binding is None:
            raise RuntimeOperationError("BINDING_NOT_FOUND")
        return binding

    def _require_work(self, work_item_id: str) -> WorkItem:
        work = self.repository.get_work_item(work_item_id)
        if work is None:
            raise RuntimeOperationError("WORK_ITEM_NOT_FOUND")
        return work

    def _require_work_attempt(self, attempt_id: str) -> WorkAttempt:
        attempt = self.repository.get_work_attempt(attempt_id)
        if attempt is None:
            raise RuntimeOperationError("WORK_ATTEMPT_NOT_FOUND")
        return attempt
