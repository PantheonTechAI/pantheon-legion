"""Same-host, restartable Aquila-outbox to Runtime-intake composition."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import os
import sqlite3
import time

from legion_runtime import PostgreSQLAgentStore
from sqlalchemy.exc import SQLAlchemyError

from legion_kernel import MissionStatus
from legion_kernel.investigation import intent_digest
from legion_runtime import RuntimeInvestigationAdmissions, InvestigationAdmissionError

from .investigation import PROFILE, InvestigationIntent
from .persistent import PersistentAquilaService


class InvestigationDispatchError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class LocalInvestigationDispatcher:
    """One bounded delivery call; the caller controls polling and backoff."""

    def __init__(self, aquila_database: str, runtime_store, *,
                 investigation_subjects: tuple[str, str]) -> None:
        self.aquila_database = aquila_database
        self.runtime_store = runtime_store
        self.investigation_subjects = investigation_subjects
        self.admissions = RuntimeInvestigationAdmissions(runtime_store)

    def dispatch(self, command_id: str) -> str:
        source = PersistentAquilaService(
            self.aquila_database,
            investigation_subjects=self.investigation_subjects,
        )
        try:
            intent = source.outbox.get_by_command(command_id)
            if intent is None:
                raise InvestigationDispatchError("INVESTIGATION_NOT_FOUND")
            if self.runtime_store.get_investigation_by_command(command_id) is None:
                intent = self._load_ready_intent(source, command_id)
            mission = source.store.get_mission(intent.mission_id)
            intake = self.admissions.admit(intent, mission)
            with source.store.transaction():
                source.outbox.acknowledge(command_id, intake.intake_id)
            return intake.intake_id
        finally:
            source.close()

    def dispatch_pending(self, limit: int = 16) -> tuple[str, ...]:
        admitted = []
        for intent in self.pending(limit):
            try:
                admitted.append(self.dispatch(intent.command_id))
            except InvestigationDispatchError as exc:
                self._record_error(intent.command_id, exc.code, retryable=exc.retryable)
            except InvestigationAdmissionError as exc:
                self._record_error(
                    intent.command_id, exc.code,
                    retryable=exc.code == "MISSION_NOT_ACTIVE",
                )
            except ValueError:
                self._record_error(intent.command_id, "INVALID_INVESTIGATION_INTENT", retryable=False)
            except (ConnectionError, OSError, TimeoutError, SQLAlchemyError, sqlite3.OperationalError):
                self._record_error(intent.command_id, "DELIVERY_UNAVAILABLE")
        return tuple(admitted)

    def _record_error(self, command_id: str, error_code: str, *, retryable: bool = True) -> None:
        source = PersistentAquilaService(
            self.aquila_database,
            investigation_subjects=self.investigation_subjects,
        )
        try:
            with source.store.transaction():
                source.outbox.record_error(command_id, error_code, retryable=retryable)
        finally:
            source.close()

    def pending(self, limit: int = 16) -> tuple[InvestigationIntent, ...]:
        source = PersistentAquilaService(
            self.aquila_database,
            investigation_subjects=self.investigation_subjects,
        )
        try:
            return source.outbox.pending(limit)
        finally:
            source.close()

    def _load_ready_intent(self, source: PersistentAquilaService, command_id: str) -> InvestigationIntent:
        intent = source.outbox.get_by_command(command_id)
        if intent is None:
            raise InvestigationDispatchError("INVESTIGATION_NOT_FOUND")
        if intent.status not in {"PENDING", "DELIVERED"}:
            raise InvestigationDispatchError("DELIVERY_BLOCKED")
        mission = source.store.get_mission(intent.mission_id)
        if mission is None:
            raise InvestigationDispatchError("MISSION_NOT_FOUND")
        if mission.status != MissionStatus.ACTIVE:
            raise InvestigationDispatchError(
                "MISSION_NOT_ACTIVE" if mission.status in {
                    MissionStatus.PAUSED, MissionStatus.SUSPENDED,
                    MissionStatus.AWAITING_APPROVAL,
                } else "MISSION_TERMINAL",
                retryable=mission.status in {
                    MissionStatus.PAUSED, MissionStatus.SUSPENDED,
                    MissionStatus.AWAITING_APPROVAL,
                },
            )
        if (mission.organization_id != intent.organization_id
                or mission.workspace_id != intent.workspace_id
                or intent.profile != PROFILE):
            raise InvestigationDispatchError("INVESTIGATION_SCOPE_MISMATCH")
        digest = intent_digest(
            command_id=intent.command_id, mission_id=intent.mission_id,
            organization_id=intent.organization_id,
            workspace_id=intent.workspace_id, objective=mission.objective,
            profile=intent.profile,
        )
        if digest != intent.intent_digest:
            raise InvestigationDispatchError("INVESTIGATION_INTENT_MISMATCH")
        grants = {grant.grant_id: grant for grant in source._list_delegations(intent.mission_id)}
        required = (
            (intent.centurion_grant_id, self.investigation_subjects[0],
             frozenset({"READ_MISSION", "INVOKE_COGNITION"})),
            (intent.scout_grant_id, self.investigation_subjects[1],
             frozenset({"READ_MISSION", "READ_KNOWLEDGE", "INVOKE_COGNITION"})),
        )
        now = datetime.now(timezone.utc)
        for grant_id, subject, operations in required:
            grant = grants.get(grant_id)
            if (grant is None or grant.revoked or grant.mission_id != intent.mission_id
                    or grant.subject.subject != subject
                    or grant.subject.type.value != "WORKLOAD"
                    or grant.issuer.subject != intent.requested_by
                    or grant.allowed_operations != operations
                    or grant.expires_at != intent.expires_at
                    or datetime.fromisoformat(grant.expires_at.replace("Z", "+00:00")) <= now):
                raise InvestigationDispatchError("INVESTIGATION_AUTHORITY_UNAVAILABLE")
        return intent


def main() -> None:
    parser = argparse.ArgumentParser(description="Deliver local Aquila investigation intents to Runtime.")
    parser.add_argument("--once", action="store_true", help="Process one bounded poll and exit")
    parser.add_argument("--interval-seconds", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.interval_seconds <= 60:
        parser.error("interval must be between 1 and 60 seconds")
    names = (
        "LEGION_DATABASE", "LEGION_RUNTIME_DATABASE_URL",
        "LEGION_CENTURION_WORKLOAD_SUBJECT", "LEGION_SCOUT_WORKLOAD_SUBJECT",
    )
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        parser.error("missing configuration: " + ", ".join(missing))
    store = PostgreSQLAgentStore(os.environ["LEGION_RUNTIME_DATABASE_URL"])
    dispatcher = LocalInvestigationDispatcher(
        os.environ["LEGION_DATABASE"], store,
        investigation_subjects=(
            os.environ["LEGION_CENTURION_WORKLOAD_SUBJECT"],
            os.environ["LEGION_SCOUT_WORKLOAD_SUBJECT"],
        ),
    )
    try:
        while True:
            try:
                dispatcher.dispatch_pending()
            except (ConnectionError, OSError, TimeoutError, SQLAlchemyError, sqlite3.OperationalError):
                # Store outages leave the durable outbox for the next bounded poll.
                if args.once:
                    raise
            if args.once:
                return
            time.sleep(args.interval_seconds)
    finally:
        store.close()


if __name__ == "__main__":
    main()
