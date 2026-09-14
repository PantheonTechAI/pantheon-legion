"""SQLite reference repository for Mission snapshots and audit records."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from legion_kernel.kernel import (
    Action,
    AuditEvent,
    Constraint,
    Mission,
    MissionStatus,
    Participant,
    Principal,
    PrincipalType,
    RulesOfEngagement,
    RoeLevel,
)


class StoreConflict(RuntimeError):
    """Raised when a Mission write loses its optimistic-concurrency race."""


class DuplicateEvent(RuntimeError):
    """Raised when an audit event would duplicate or skip a sequence."""


class SQLiteMissionStore:
    """Inspectable SQLite repository for the M1 Mission aggregate.

    The repository owns transactions and enforces Mission version and audit
    sequence invariants. It does not decide authorization or ROE; those remain
    kernel/control-plane responsibilities.
    """

    def __init__(self, database: str | Path | sqlite3.Connection) -> None:
        if isinstance(database, sqlite3.Connection):
            self.connection = database
            self._owns_connection = False
        else:
            self.connection = sqlite3.connect(str(database))
            self._owns_connection = True
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._transaction_depth = 0
        self._initialize()

    def close(self) -> None:
        if self._owns_connection:
            self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit a group of repository changes atomically.

        Repository methods are safe to compose: inner writes join an outer
        transaction instead of committing a partial authority record.
        """
        outermost = self._transaction_depth == 0
        if outermost:
            self.connection.execute("BEGIN IMMEDIATE")
        self._transaction_depth += 1
        try:
            yield
        except Exception:
            if outermost:
                self.connection.rollback()
            raise
        else:
            if outermost:
                self.connection.commit()
        finally:
            self._transaction_depth -= 1

    def save_mission(self, mission: Mission, *, expected_previous_version: int | None) -> None:
        payload = json.dumps(_mission_payload(mission), sort_keys=True)
        now = mission.updated_at
        with self.transaction():
            if expected_previous_version is None:
                try:
                    self.connection.execute(
                        "INSERT INTO missions (id, version, updated_at, payload) VALUES (?, ?, ?, ?)",
                        (mission.id, mission.version, now, payload),
                    )
                except sqlite3.IntegrityError as exc:
                    raise StoreConflict(f"Mission {mission.id} already exists") from exc
                return

            updated = self.connection.execute(
                """
                UPDATE missions
                   SET version = ?, updated_at = ?, payload = ?
                 WHERE id = ? AND version = ?
                """,
                (mission.version, now, payload, mission.id, expected_previous_version),
            ).rowcount
            if updated != 1:
                raise StoreConflict(
                    f"Mission {mission.id} expected version {expected_previous_version}"
                )

    def get_mission(self, mission_id: str) -> Mission | None:
        row = self.connection.execute(
            "SELECT payload FROM missions WHERE id = ?", (mission_id,)
        ).fetchone()
        return _mission_from_payload(json.loads(row["payload"])) if row else None

    def list_mission_ids(self) -> list[str]:
        rows = self.connection.execute("SELECT id FROM missions ORDER BY id").fetchall()
        return [row["id"] for row in rows]

    def append_audit(self, event: AuditEvent) -> None:
        with self.transaction():
            row = self.connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM audit_events WHERE mission_id = ?",
                (event.mission_id,),
            ).fetchone()
            expected_sequence = int(row["sequence"]) + 1
            if event.sequence != expected_sequence:
                raise DuplicateEvent(
                    f"Expected audit sequence {expected_sequence}, got {event.sequence}"
                )
            try:
                self.connection.execute(
                    """
                    INSERT INTO audit_events
                      (id, mission_id, sequence, mission_version, event_type,
                       occurred_at, actor, result, correlation_id, command_id,
                       approval_id, causation_id, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.id,
                        event.mission_id,
                        event.sequence,
                        event.mission_version,
                        event.event_type,
                        event.occurred_at,
                        json.dumps(_principal_payload(event.actor), sort_keys=True),
                        event.result,
                        event.correlation_id,
                        event.command_id,
                        event.approval_id,
                        event.causation_id,
                        json.dumps(event.data, sort_keys=True),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateEvent(f"Audit event {event.id} already exists") from exc

    def get_audit(self, mission_id: str) -> list[AuditEvent]:
        rows = self.connection.execute(
            "SELECT * FROM audit_events WHERE mission_id = ? ORDER BY sequence",
            (mission_id,),
        ).fetchall()
        return [
            AuditEvent(
                id=row["id"],
                sequence=row["sequence"],
                mission_id=row["mission_id"],
                mission_version=row["mission_version"],
                event_type=row["event_type"],
                occurred_at=row["occurred_at"],
                actor=_principal_from_payload(json.loads(row["actor"])),
                result=row["result"],
                correlation_id=row["correlation_id"],
                command_id=row["command_id"],
                approval_id=row["approval_id"],
                causation_id=row["causation_id"],
                data=json.loads(row["data"]),
            )
            for row in rows
        ]

    def put_idempotency(
        self,
        *,
        mission_id: str,
        idempotency_key: str,
        fingerprint: str,
        result: dict[str, Any],
    ) -> None:
        with self.transaction():
            try:
                self.connection.execute(
                    """
                    INSERT INTO idempotency_keys
                      (mission_id, idempotency_key, fingerprint, result)
                    VALUES (?, ?, ?, ?)
                    """,
                    (mission_id, idempotency_key, fingerprint, json.dumps(result, sort_keys=True)),
                )
            except sqlite3.IntegrityError as exc:
                raise StoreConflict("Idempotency key already exists") from exc

    def get_idempotency(self, *, mission_id: str, idempotency_key: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT fingerprint, result FROM idempotency_keys
             WHERE mission_id = ? AND idempotency_key = ?
            """,
            (mission_id, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        return {"fingerprint": row["fingerprint"], "result": json.loads(row["result"])}

    def _initialize(self) -> None:
        self.connection.executescript(
            """
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    sequence INTEGER NOT NULL,
                    mission_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    result TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    command_id TEXT,
                    approval_id TEXT,
                    causation_id TEXT,
                    data TEXT NOT NULL,
                    UNIQUE (mission_id, sequence),
                    UNIQUE (mission_id, id)
                );
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    idempotency_key TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    result TEXT NOT NULL,
                    PRIMARY KEY (mission_id, idempotency_key)
                );
            """
        )


def _principal_payload(principal: Principal) -> dict[str, Any]:
    return {
        "type": principal.type.value,
        "subject": principal.subject,
        "roles": sorted(principal.roles),
    }


def _principal_from_payload(payload: dict[str, Any]) -> Principal:
    return Principal(
        type=PrincipalType(payload["type"]),
        subject=payload["subject"],
        roles=frozenset(payload.get("roles", [])),
    )


def _action_payload(action: Action) -> dict[str, Any]:
    return {
        "id": action.id,
        "command_id": action.command_id,
        "capability": action.capability,
        "arguments": action.arguments,
        "target": action.target,
        "side_effect_class": action.side_effect_class,
        "requested_by": _principal_payload(action.requested_by),
        "requested_at": action.requested_at,
    }


def _action_from_payload(payload: dict[str, Any]) -> Action:
    return Action(
        id=payload["id"],
        command_id=payload.get("command_id", payload["id"]),
        capability=payload["capability"],
        arguments=payload["arguments"],
        target=payload["target"],
        side_effect_class=payload["side_effect_class"],
        requested_by=_principal_from_payload(payload["requested_by"]),
        requested_at=payload["requested_at"],
    )


def _mission_payload(mission: Mission) -> dict[str, Any]:
    roe = mission.roe
    return {
        "id": mission.id,
        "organization_id": mission.organization_id,
        "workspace_id": mission.workspace_id,
        "title": mission.title,
        "objective": mission.objective,
        "created_by": _principal_payload(mission.created_by),
        "status": mission.status.value,
        "version": mission.version,
        "roe": {
            "revision": roe.revision,
            "level": roe.level.value,
            "changed_by": _principal_payload(roe.changed_by),
            "effective_at": roe.effective_at,
            "approval_required_for": sorted(roe.approval_required_for),
            "allowed_capabilities": sorted(roe.allowed_capabilities),
            "denied_capabilities": sorted(roe.denied_capabilities),
            "reason": roe.reason,
        },
        "constraints": [
            {
                "id": item.id,
                "text": item.text,
                "severity": item.severity,
                "added_by": _principal_payload(item.added_by),
                "added_at": item.added_at,
            }
            for item in mission.constraints
        ],
        "participants": [
            {
                "principal": _principal_payload(item.principal),
                "role": item.role,
                "scope": item.scope,
            }
            for item in mission.participants
        ],
        "created_at": mission.created_at,
        "updated_at": mission.updated_at,
        "actions": {key: _action_payload(value) for key, value in mission.actions.items()},
    }


def _mission_from_payload(payload: dict[str, Any]) -> Mission:
    roe_payload = payload["roe"]
    return Mission(
        id=payload["id"],
        organization_id=payload["organization_id"],
        workspace_id=payload["workspace_id"],
        title=payload["title"],
        objective=payload["objective"],
        created_by=_principal_from_payload(payload["created_by"]),
        status=MissionStatus(payload["status"]),
        version=payload["version"],
        roe=RulesOfEngagement(
            revision=roe_payload["revision"],
            level=RoeLevel(roe_payload["level"]),
            changed_by=_principal_from_payload(roe_payload["changed_by"]),
            effective_at=roe_payload["effective_at"],
            approval_required_for=frozenset(roe_payload["approval_required_for"]),
            allowed_capabilities=frozenset(roe_payload["allowed_capabilities"]),
            denied_capabilities=frozenset(roe_payload["denied_capabilities"]),
            reason=roe_payload["reason"],
        ),
        constraints=[
            Constraint(
                id=item["id"],
                text=item["text"],
                severity=item["severity"],
                added_by=_principal_from_payload(item["added_by"]),
                added_at=item["added_at"],
            )
            for item in payload["constraints"]
        ],
        participants=[
            Participant(
                principal=_principal_from_payload(item["principal"]),
                role=item["role"],
                scope=item.get("scope"),
            )
            for item in payload.get("participants", [])
        ],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
        actions={key: _action_from_payload(value) for key, value in payload["actions"].items()},
    )
