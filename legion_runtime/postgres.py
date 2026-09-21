"""PostgreSQL persistence for Legion Runtime Agent state."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Mapping, Any

from sqlalchemy import Engine, create_engine, func, insert, select, text, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

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
    NextIntent,
    RuntimeEvent,
)
from .database import (
    agents,
    coordination_checkpoints,
    mission_assignments,
    runtime_bindings,
    runtime_events,
    runtime_idempotency,
    runtime_work_attempts,
    runtime_work_evidence_references,
    runtime_work_items,
    runtime_work_results,
)
from .repository import AgentStoreConflict, DuplicateRuntimeEvent, IdempotencyRecord

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
)

class PostgreSQLAgentStore:
    """Runtime-owned PostgreSQL repository with explicit transaction locking."""

    def __init__(self, database_url: str, *, engine: Engine | None = None) -> None:
        if not isinstance(database_url, str) or not database_url.strip():
            raise ValueError("database_url is required")
        self.engine = engine or create_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
        )
        self._owns_engine = engine is None
        self._connection: Connection | None = None
        self._transaction_depth = 0

    def close(self) -> None:
        if self._connection is not None:
            raise RuntimeError("cannot close store during a transaction")
        if self._owns_engine:
            self.engine.dispose()

    @contextmanager
    def transaction(
        self,
        *,
        lock_key: str | None = None,
        lock_keys: tuple[str, ...] | None = None,
    ) -> Iterator[None]:
        requested = list(lock_keys or ())
        if lock_key is not None:
            requested.append(lock_key)
        if not requested or any(
            not isinstance(value, str) or not value.strip() for value in requested
        ):
            raise ValueError("transaction requires non-empty lock keys")
        ordered_keys = tuple(sorted(set(requested)))
        if self._connection is not None:
            self._transaction_depth += 1
            try:
                for value in ordered_keys:
                    self._acquire_lock(value)
                yield
            finally:
                self._transaction_depth -= 1
            return
        with self.engine.connect() as connection:
            transaction = connection.begin()
            self._connection = connection
            self._transaction_depth = 1
            try:
                for value in ordered_keys:
                    self._acquire_lock(value)
                yield
            except Exception:
                transaction.rollback()
                raise
            else:
                transaction.commit()
            finally:
                self._transaction_depth = 0
                self._connection = None

    def save_agent(
        self, agent: AgentIdentity, *, expected_previous_version: int | None
    ) -> None:
        values = {
            "agent_id": agent.agent_id,
            "organization_id": agent.organization_id,
            "workspace_id": agent.workspace_id,
            "display_name": agent.display_name,
            "role": agent.role.value,
            "status": agent.status.value,
            "version": agent.version,
            "created_by_type": agent.created_by.type,
            "created_by_subject": agent.created_by.subject,
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }
        if expected_previous_version is None:
            self._insert(agents, values, "AGENT_ALREADY_EXISTS")
            return
        statement = (
            update(agents)
            .where(
                agents.c.agent_id == agent.agent_id,
                agents.c.version == expected_previous_version,
            )
            .values(**{key: value for key, value in values.items() if key != "agent_id"})
        )
        self._require_updated(statement, "AGENT_VERSION_CONFLICT")

    def get_agent(self, agent_id: str) -> AgentIdentity | None:
        row = self._one(select(agents).where(agents.c.agent_id == agent_id))
        return self._agent(row) if row else None

    def save_assignment(
        self,
        assignment: MissionAssignment,
        *,
        expected_previous_version: int | None,
    ) -> None:
        values = {
            "assignment_id": assignment.assignment_id,
            "agent_id": assignment.agent_id,
            "mission_id": assignment.mission_id,
            "status": assignment.status.value,
            "mission_version": assignment.mission_version,
            "authorization_decision_id": assignment.authorization_decision_id,
            "policy_version": assignment.policy_version,
            "requested_by_type": assignment.requested_by.type,
            "requested_by_subject": assignment.requested_by.subject,
            "correlation_id": assignment.correlation_id,
            "last_error_code": assignment.last_error_code,
            "version": assignment.version,
            "created_at": assignment.created_at,
            "updated_at": assignment.updated_at,
        }
        if expected_previous_version is None:
            self._insert(mission_assignments, values, "ASSIGNMENT_CONFLICT")
            return
        statement = (
            update(mission_assignments)
            .where(
                mission_assignments.c.assignment_id == assignment.assignment_id,
                mission_assignments.c.version == expected_previous_version,
            )
            .values(
                **{
                    key: value
                    for key, value in values.items()
                    if key != "assignment_id"
                }
            )
        )
        self._require_updated(statement, "ASSIGNMENT_VERSION_CONFLICT")

    def get_assignment(self, assignment_id: str) -> MissionAssignment | None:
        row = self._one(
            select(mission_assignments).where(
                mission_assignments.c.assignment_id == assignment_id
            )
        )
        return self._assignment(row) if row else None

    def list_assignments_for_mission(self, mission_id: str) -> list[MissionAssignment]:
        rows = self._all(
            select(mission_assignments)
            .where(mission_assignments.c.mission_id == mission_id)
            .order_by(
                mission_assignments.c.created_at,
                mission_assignments.c.assignment_id,
            )
        )
        return [self._assignment(row) for row in rows]

    def get_active_assignment(self, agent_id: str) -> MissionAssignment | None:
        row = self._one(
            select(mission_assignments)
            .where(
                mission_assignments.c.agent_id == agent_id,
                mission_assignments.c.status.in_(
                    (
                        AssignmentStatus.PENDING_AUTHORIZATION.value,
                        AssignmentStatus.ASSIGNED.value,
                        AssignmentStatus.BLOCKED.value,
                    )
                ),
            )
            .order_by(mission_assignments.c.created_at.desc())
            .limit(1)
        )
        return self._assignment(row) if row else None

    def save_checkpoint(
        self,
        checkpoint: CoordinationCheckpoint,
        *,
        expected_previous_revision: int | None,
    ) -> None:
        values = {
            "assignment_id": checkpoint.assignment_id,
            "revision": checkpoint.revision,
            "state": checkpoint.state.value,
            "next_intent": checkpoint.next_intent.value,
            "last_observed_mission_version": checkpoint.last_observed_mission_version,
            "correlation_id": checkpoint.correlation_id,
            "last_error_code": checkpoint.last_error_code,
            "updated_at": checkpoint.updated_at,
            "focus_work_item_id": checkpoint.focus_work_item_id,
        }
        if expected_previous_revision is None:
            self._insert(coordination_checkpoints, values, "CHECKPOINT_CONFLICT")
            return
        statement = (
            update(coordination_checkpoints)
            .where(
                coordination_checkpoints.c.assignment_id == checkpoint.assignment_id,
                coordination_checkpoints.c.revision == expected_previous_revision,
            )
            .values(
                **{
                    key: value
                    for key, value in values.items()
                    if key != "assignment_id"
                }
            )
        )
        self._require_updated(statement, "CHECKPOINT_REVISION_CONFLICT")

    def get_checkpoint(self, assignment_id: str) -> CoordinationCheckpoint | None:
        row = self._one(
            select(coordination_checkpoints).where(
                coordination_checkpoints.c.assignment_id == assignment_id
            )
        )
        return self._checkpoint(row) if row else None

    def save_binding(
        self,
        binding: AgentRuntimeBinding,
        *,
        expected_previous_version: int | None,
    ) -> None:
        values = {
            "binding_id": binding.binding_id,
            "agent_id": binding.agent_id,
            "assignment_id": binding.assignment_id,
            "workload_subject": binding.workload_subject,
            "grant_id": binding.grant_id,
            "status": binding.status.value,
            "version": binding.version,
            "started_at": binding.started_at,
            "ended_at": binding.ended_at,
            "correlation_id": binding.correlation_id,
            "last_error_code": binding.last_error_code,
        }
        if expected_previous_version is None:
            self._insert(runtime_bindings, values, "BINDING_CONFLICT")
            return
        statement = (
            update(runtime_bindings)
            .where(
                runtime_bindings.c.binding_id == binding.binding_id,
                runtime_bindings.c.version == expected_previous_version,
            )
            .values(
                **{
                    key: value
                    for key, value in values.items()
                    if key != "binding_id"
                }
            )
        )
        self._require_updated(statement, "BINDING_VERSION_CONFLICT")

    def get_binding(self, binding_id: str) -> AgentRuntimeBinding | None:
        row = self._one(
            select(runtime_bindings).where(runtime_bindings.c.binding_id == binding_id)
        )
        return self._binding(row) if row else None

    def get_active_binding(self, assignment_id: str) -> AgentRuntimeBinding | None:
        row = self._one(
            select(runtime_bindings)
            .where(
                runtime_bindings.c.assignment_id == assignment_id,
                runtime_bindings.c.status == BindingStatus.ACTIVE.value,
            )
            .limit(1)
        )
        return self._binding(row) if row else None

    def list_bindings(self, assignment_id: str) -> list[AgentRuntimeBinding]:
        rows = self._all(
            select(runtime_bindings)
            .where(runtime_bindings.c.assignment_id == assignment_id)
            .order_by(runtime_bindings.c.started_at, runtime_bindings.c.binding_id)
        )
        return [self._binding(row) for row in rows]

    def save_work_item(
        self, work_item: WorkItem, *, expected_previous_version: int | None
    ) -> None:
        values = {
            "work_item_id": work_item.work_item_id,
            "mission_id": work_item.mission_id,
            "centurion_agent_id": work_item.centurion_agent_id,
            "centurion_assignment_id": work_item.centurion_assignment_id,
            "scout_agent_id": work_item.scout_agent_id,
            "scout_assignment_id": work_item.scout_assignment_id,
            "objective": work_item.objective,
            "required_capabilities": list(work_item.required_capabilities),
            "work_kind": work_item.kind.value,
            "status": work_item.status.value,
            "version": work_item.version,
            "correlation_id": work_item.correlation_id,
            "causation_id": work_item.causation_id,
            "created_at": work_item.created_at,
            "updated_at": work_item.updated_at,
            "cancelled_at": work_item.cancelled_at,
            "cancellation_reason": work_item.cancellation_reason,
        }
        if expected_previous_version is None:
            self._insert(runtime_work_items, values, "WORK_ITEM_CONFLICT")
            return
        statement = (
            update(runtime_work_items)
            .where(
                runtime_work_items.c.work_item_id == work_item.work_item_id,
                runtime_work_items.c.version == expected_previous_version,
            )
            .values(
                **{
                    key: value
                    for key, value in values.items()
                    if key != "work_item_id"
                }
            )
        )
        self._require_updated(statement, "WORK_ITEM_VERSION_CONFLICT")

    def get_work_item(self, work_item_id: str) -> WorkItem | None:
        row = self._one(
            select(runtime_work_items).where(
                runtime_work_items.c.work_item_id == work_item_id
            )
        )
        return self._work_item(row) if row else None

    def list_work_for_assignment(self, assignment_id: str) -> list[WorkItem]:
        rows = self._all(
            select(runtime_work_items)
            .where(
                (runtime_work_items.c.centurion_assignment_id == assignment_id)
                | (runtime_work_items.c.scout_assignment_id == assignment_id)
            )
            .order_by(runtime_work_items.c.created_at, runtime_work_items.c.work_item_id)
        )
        return [self._work_item(row) for row in rows]

    def list_work_for_mission(self, mission_id: str) -> list[WorkItem]:
        rows = self._all(
            select(runtime_work_items)
            .where(runtime_work_items.c.mission_id == mission_id)
            .order_by(runtime_work_items.c.created_at, runtime_work_items.c.work_item_id)
        )
        return [self._work_item(row) for row in rows]

    def save_work_attempt(
        self, attempt: WorkAttempt, *, expected_previous_version: int | None
    ) -> None:
        values = {
            "attempt_id": attempt.attempt_id,
            "work_item_id": attempt.work_item_id,
            "scout_agent_id": attempt.scout_agent_id,
            "scout_binding_id": attempt.scout_binding_id,
            "status": attempt.status.value,
            "attempt_number": attempt.attempt_number,
            "mission_version": attempt.mission_version,
            "authorization_decision_id": attempt.authorization_decision_id,
            "attempt_stage": (
                attempt.attempt_stage.value if attempt.attempt_stage is not None else None
            ),
            "knowledge_authorization_decision_ids": list(
                attempt.knowledge_authorization_decision_ids
            ),
            "successful_knowledge_decision_id": attempt.successful_knowledge_decision_id,
            "evidence_correlation_id": attempt.evidence_correlation_id,
            "tabula_audit_correlation_id": attempt.tabula_audit_correlation_id,
            "error_code": attempt.error_code,
            "version": attempt.version,
            "created_at": attempt.created_at,
            "updated_at": attempt.updated_at,
        }
        if expected_previous_version is None:
            self._insert(runtime_work_attempts, values, "WORK_ATTEMPT_CONFLICT")
            return
        statement = (
            update(runtime_work_attempts)
            .where(
                runtime_work_attempts.c.attempt_id == attempt.attempt_id,
                runtime_work_attempts.c.version == expected_previous_version,
            )
            .values(
                **{
                    key: value
                    for key, value in values.items()
                    if key != "attempt_id"
                }
            )
        )
        self._require_updated(statement, "WORK_ATTEMPT_VERSION_CONFLICT")

    def get_work_attempt(self, attempt_id: str) -> WorkAttempt | None:
        row = self._one(
            select(runtime_work_attempts).where(
                runtime_work_attempts.c.attempt_id == attempt_id
            )
        )
        return self._work_attempt(row) if row else None

    def get_latest_work_attempt(self, work_item_id: str) -> WorkAttempt | None:
        row = self._one(
            select(runtime_work_attempts)
            .where(runtime_work_attempts.c.work_item_id == work_item_id)
            .order_by(runtime_work_attempts.c.attempt_number.desc())
            .limit(1)
        )
        return self._work_attempt(row) if row else None

    def list_work_attempts(self, work_item_id: str) -> list[WorkAttempt]:
        rows = self._all(
            select(runtime_work_attempts)
            .where(runtime_work_attempts.c.work_item_id == work_item_id)
            .order_by(runtime_work_attempts.c.attempt_number)
        )
        return [self._work_attempt(row) for row in rows]

    def save_work_result(self, result: WorkResult) -> None:
        self._insert(
            runtime_work_results,
            {
                "result_id": result.result_id,
                "work_item_id": result.work_item_id,
                "attempt_id": result.attempt_id,
                "scout_agent_id": result.scout_agent_id,
                "scout_binding_id": result.scout_binding_id,
                "mission_version": result.mission_version,
                "summary": result.summary,
                "evidence_references": list(result.evidence_references),
                "content_digest": result.content_digest,
                "produced_at": result.produced_at,
            },
            "WORK_RESULT_CONFLICT",
        )

    def get_work_result(self, work_item_id: str) -> WorkResult | None:
        row = self._one(
            select(runtime_work_results).where(
                runtime_work_results.c.work_item_id == work_item_id
            )
        )
        return self._work_result(row) if row else None

    def save_work_evidence_reference(self, reference: WorkEvidenceReference) -> None:
        self._insert(
            runtime_work_evidence_references,
            {
                "evidence_reference_id": reference.evidence_reference_id,
                "work_item_id": reference.work_item_id,
                "attempt_id": reference.attempt_id,
                "source_type": reference.source_type.value,
                "external_record_id": reference.external_record_id,
                "external_revision": reference.external_revision,
                "canonical_uri": reference.canonical_uri,
                "scope_binding_id": reference.scope_binding_id,
                "scope_binding_version": reference.scope_binding_version,
                "successful_authorization_decision_id": reference.successful_authorization_decision_id,
                "tabula_audit_correlation_id": reference.tabula_audit_correlation_id,
                "retrieved_at": reference.retrieved_at,
                "created_at": reference.created_at,
            },
            "WORK_EVIDENCE_REFERENCE_CONFLICT",
        )

    def list_work_evidence_references(
        self, *, work_item_id: str | None = None, attempt_id: str | None = None
    ) -> list[WorkEvidenceReference]:
        if (work_item_id is None) == (attempt_id is None):
            raise ValueError("exactly one evidence reference selector is required")
        statement = select(runtime_work_evidence_references)
        if work_item_id is not None:
            statement = statement.where(
                runtime_work_evidence_references.c.work_item_id == work_item_id
            )
        else:
            statement = statement.where(
                runtime_work_evidence_references.c.attempt_id == attempt_id
            )
        rows = self._all(statement.order_by(runtime_work_evidence_references.c.created_at, runtime_work_evidence_references.c.evidence_reference_id))
        return [self._work_evidence_reference(row) for row in rows]

    def append_event(self, event: RuntimeEvent) -> None:
        if event.sequence != self.next_event_sequence(event.agent_id):
            raise DuplicateRuntimeEvent("RUNTIME_EVENT_SEQUENCE_CONFLICT")
        values = {
            "event_id": event.event_id,
            "sequence": event.sequence,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "agent_id": event.agent_id,
            "actor_type": event.actor.type,
            "actor_subject": event.actor.subject,
            "result": event.result,
            "correlation_id": event.correlation_id,
            "mission_id": event.mission_id,
            "assignment_id": event.assignment_id,
            "binding_id": event.binding_id,
            "causation_id": event.causation_id,
            "data": event.data,
        }
        try:
            self._write().execute(insert(runtime_events).values(**values))
        except IntegrityError as exc:
            raise DuplicateRuntimeEvent("RUNTIME_EVENT_CONFLICT") from exc

    def list_events(self, agent_id: str) -> list[RuntimeEvent]:
        rows = self._all(
            select(runtime_events)
            .where(runtime_events.c.agent_id == agent_id)
            .order_by(runtime_events.c.sequence)
        )
        return [self._event(row) for row in rows]

    def next_event_sequence(self, agent_id: str) -> int:
        statement = select(func.coalesce(func.max(runtime_events.c.sequence), 0) + 1).where(
            runtime_events.c.agent_id == agent_id
        )
        if self._connection is not None:
            return int(self._connection.execute(statement).scalar_one())
        with self.engine.connect() as connection:
            return int(connection.execute(statement).scalar_one())

    def put_idempotency(self, record: IdempotencyRecord) -> None:
        self._insert(
            runtime_idempotency,
            {
                "scope": record.scope,
                "operation": record.operation,
                "idempotency_key": record.idempotency_key,
                "fingerprint": record.fingerprint,
                "resource_type": record.resource_type,
                "resource_id": record.resource_id,
            },
            "IDEMPOTENCY_CONFLICT",
        )

    def get_idempotency(
        self, *, scope: str, operation: str, idempotency_key: str
    ) -> IdempotencyRecord | None:
        row = self._one(
            select(runtime_idempotency).where(
                runtime_idempotency.c.scope == scope,
                runtime_idempotency.c.operation == operation,
                runtime_idempotency.c.idempotency_key == idempotency_key,
            )
        )
        return IdempotencyRecord(**dict(row)) if row else None

    def _acquire_lock(self, lock_key: str) -> None:
        self._write().execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": lock_key},
        )

    def _write(self) -> Connection:
        if self._connection is None:
            raise RuntimeError("repository writes require transaction()")
        return self._connection

    def _insert(self, table, values: dict[str, Any], code: str) -> None:
        try:
            self._write().execute(insert(table).values(**values))
        except IntegrityError as exc:
            raise AgentStoreConflict(code) from exc

    def _require_updated(self, statement, code: str) -> None:
        result = self._write().execute(statement)
        if result.rowcount != 1:
            raise AgentStoreConflict(code)

    def _one(self, statement) -> Mapping[str, Any] | None:
        if self._connection is not None:
            return self._connection.execute(statement).mappings().first()
        with self.engine.connect() as connection:
            return connection.execute(statement).mappings().first()

    def _all(self, statement) -> list[Mapping[str, Any]]:
        if self._connection is not None:
            return list(self._connection.execute(statement).mappings().all())
        with self.engine.connect() as connection:
            return list(connection.execute(statement).mappings().all())

    @staticmethod
    def _agent(row: Mapping[str, Any]) -> AgentIdentity:
        return AgentIdentity(
            agent_id=row["agent_id"],
            organization_id=row["organization_id"],
            workspace_id=row["workspace_id"],
            display_name=row["display_name"],
            role=AgentRole(row["role"]),
            status=AgentStatus(row["status"]),
            version=row["version"],
            created_by=ActorRef(row["created_by_type"], row["created_by_subject"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _assignment(row: Mapping[str, Any]) -> MissionAssignment:
        return MissionAssignment(
            assignment_id=row["assignment_id"],
            agent_id=row["agent_id"],
            mission_id=row["mission_id"],
            status=AssignmentStatus(row["status"]),
            mission_version=row["mission_version"],
            authorization_decision_id=row["authorization_decision_id"],
            policy_version=row["policy_version"],
            requested_by=ActorRef(row["requested_by_type"], row["requested_by_subject"]),
            correlation_id=row["correlation_id"],
            last_error_code=row["last_error_code"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _checkpoint(row: Mapping[str, Any]) -> CoordinationCheckpoint:
        return CoordinationCheckpoint(
            assignment_id=row["assignment_id"],
            revision=row["revision"],
            state=CheckpointState(row["state"]),
            next_intent=NextIntent(row["next_intent"]),
            last_observed_mission_version=row["last_observed_mission_version"],
            correlation_id=row["correlation_id"],
            last_error_code=row["last_error_code"],
            updated_at=row["updated_at"],
            focus_work_item_id=row["focus_work_item_id"],
        )

    @staticmethod
    def _binding(row: Mapping[str, Any]) -> AgentRuntimeBinding:
        return AgentRuntimeBinding(
            binding_id=row["binding_id"],
            agent_id=row["agent_id"],
            assignment_id=row["assignment_id"],
            workload_subject=row["workload_subject"],
            grant_id=row["grant_id"],
            status=BindingStatus(row["status"]),
            version=row["version"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            correlation_id=row["correlation_id"],
            last_error_code=row["last_error_code"],
        )

    @staticmethod
    def _work_item(row: Mapping[str, Any]) -> WorkItem:
        return WorkItem(
            work_item_id=row["work_item_id"],
            mission_id=row["mission_id"],
            centurion_agent_id=row["centurion_agent_id"],
            centurion_assignment_id=row["centurion_assignment_id"],
            scout_agent_id=row["scout_agent_id"],
            scout_assignment_id=row["scout_assignment_id"],
            objective=row["objective"],
            required_capabilities=tuple(row["required_capabilities"]),
            kind=WorkKind(row["work_kind"]),
            status=WorkStatus(row["status"]),
            version=row["version"],
            correlation_id=row["correlation_id"],
            causation_id=row["causation_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            cancelled_at=row["cancelled_at"],
            cancellation_reason=row["cancellation_reason"],
        )

    @staticmethod
    def _work_attempt(row: Mapping[str, Any]) -> WorkAttempt:
        return WorkAttempt(
            attempt_id=row["attempt_id"],
            work_item_id=row["work_item_id"],
            scout_agent_id=row["scout_agent_id"],
            scout_binding_id=row["scout_binding_id"],
            status=AttemptStatus(row["status"]),
            attempt_number=row["attempt_number"],
            mission_version=row["mission_version"],
            authorization_decision_id=row["authorization_decision_id"],
            attempt_stage=(
                AttemptStage(row["attempt_stage"]) if row["attempt_stage"] else None
            ),
            knowledge_authorization_decision_ids=tuple(
                row["knowledge_authorization_decision_ids"] or ()
            ),
            successful_knowledge_decision_id=row["successful_knowledge_decision_id"],
            evidence_correlation_id=row["evidence_correlation_id"],
            tabula_audit_correlation_id=row["tabula_audit_correlation_id"],
            error_code=row["error_code"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _work_evidence_reference(row: Mapping[str, Any]) -> WorkEvidenceReference:
        return WorkEvidenceReference(
            evidence_reference_id=row["evidence_reference_id"],
            work_item_id=row["work_item_id"],
            attempt_id=row["attempt_id"],
            source_type=EvidenceSourceType(row["source_type"]),
            external_record_id=row["external_record_id"],
            external_revision=row["external_revision"],
            canonical_uri=row["canonical_uri"],
            scope_binding_id=row["scope_binding_id"],
            scope_binding_version=row["scope_binding_version"],
            successful_authorization_decision_id=row[
                "successful_authorization_decision_id"
            ],
            tabula_audit_correlation_id=row["tabula_audit_correlation_id"],
            retrieved_at=row["retrieved_at"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _work_result(row: Mapping[str, Any]) -> WorkResult:
        return WorkResult(
            result_id=row["result_id"],
            work_item_id=row["work_item_id"],
            attempt_id=row["attempt_id"],
            scout_agent_id=row["scout_agent_id"],
            scout_binding_id=row["scout_binding_id"],
            mission_version=row["mission_version"],
            summary=row["summary"],
            evidence_references=tuple(row["evidence_references"]),
            content_digest=row["content_digest"],
            produced_at=row["produced_at"],
        )

    @staticmethod
    def _event(row: Mapping[str, Any]) -> RuntimeEvent:
        return RuntimeEvent(
            event_id=row["event_id"],
            sequence=row["sequence"],
            event_type=row["event_type"],
            occurred_at=row["occurred_at"],
            agent_id=row["agent_id"],
            actor=ActorRef(row["actor_type"], row["actor_subject"]),
            result=row["result"],
            correlation_id=row["correlation_id"],
            mission_id=row["mission_id"],
            assignment_id=row["assignment_id"],
            binding_id=row["binding_id"],
            causation_id=row["causation_id"],
            data=dict(row["data"]),
        )
