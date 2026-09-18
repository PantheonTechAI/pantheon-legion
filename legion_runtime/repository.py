"""Repository contract for persistent Agent identity and coordination state."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from .agent import (
    AgentIdentity,
    AgentRuntimeBinding,
    CoordinationCheckpoint,
    MissionAssignment,
    RuntimeEvent,
)

from .work import WorkAttempt, WorkItem, WorkResult

class AgentStoreConflict(RuntimeError):
    pass


class DuplicateRuntimeEvent(RuntimeError):
    pass


@dataclass(frozen=True)
class IdempotencyRecord:
    scope: str
    operation: str
    idempotency_key: str
    fingerprint: str
    resource_type: str
    resource_id: str


class AgentRepository(Protocol):
    def transaction(
        self,
        *,
        lock_key: str | None = None,
        lock_keys: tuple[str, ...] | None = None,
    ) -> AbstractContextManager[None]: ...

    def close(self) -> None: ...

    def save_agent(
        self, agent: AgentIdentity, *, expected_previous_version: int | None
    ) -> None: ...

    def get_agent(self, agent_id: str) -> AgentIdentity | None: ...

    def save_assignment(
        self,
        assignment: MissionAssignment,
        *,
        expected_previous_version: int | None,
    ) -> None: ...

    def get_assignment(self, assignment_id: str) -> MissionAssignment | None: ...

    def get_active_assignment(self, agent_id: str) -> MissionAssignment | None: ...

    def save_checkpoint(
        self,
        checkpoint: CoordinationCheckpoint,
        *,
        expected_previous_revision: int | None,
    ) -> None: ...

    def get_checkpoint(self, assignment_id: str) -> CoordinationCheckpoint | None: ...

    def save_binding(
        self,
        binding: AgentRuntimeBinding,
        *,
        expected_previous_version: int | None,
    ) -> None: ...

    def get_binding(self, binding_id: str) -> AgentRuntimeBinding | None: ...

    def get_active_binding(self, assignment_id: str) -> AgentRuntimeBinding | None: ...

    def list_bindings(self, assignment_id: str) -> list[AgentRuntimeBinding]: ...


    def save_work_item(
        self, work_item: WorkItem, *, expected_previous_version: int | None
    ) -> None: ...
    def get_work_item(self, work_item_id: str) -> WorkItem | None: ...
    def list_work_for_assignment(self, assignment_id: str) -> list[WorkItem]: ...
    def save_work_attempt(
        self, attempt: WorkAttempt, *, expected_previous_version: int | None
    ) -> None: ...
    def get_work_attempt(self, attempt_id: str) -> WorkAttempt | None: ...
    def get_latest_work_attempt(self, work_item_id: str) -> WorkAttempt | None: ...
    def list_work_attempts(self, work_item_id: str) -> list[WorkAttempt]: ...
    def save_work_result(self, result: WorkResult) -> None: ...
    def get_work_result(self, work_item_id: str) -> WorkResult | None: ...
    def append_event(self, event: RuntimeEvent) -> None: ...

    def list_events(self, agent_id: str) -> list[RuntimeEvent]: ...

    def next_event_sequence(self, agent_id: str) -> int: ...

    def put_idempotency(self, record: IdempotencyRecord) -> None: ...

    def get_idempotency(
        self, *, scope: str, operation: str, idempotency_key: str
    ) -> IdempotencyRecord | None: ...
