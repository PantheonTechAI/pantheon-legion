"""Aquila-owned local delivery record for a bounded Mission investigation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import sqlite3
import re
from typing import Any

from legion_kernel.investigation import intent_digest


PROFILE = "READ_ONLY_CORPUS_V1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class InvestigationIntent:
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
    correlation_id: str
    requested_by: str
    status: str = "PENDING"
    intake_id: str | None = None
    last_error_code: str | None = None


class SQLiteInvestigationOutbox:
    """Transport metadata only; Mission, audit and grant rows are untouched."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def initialize(self) -> None:
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS investigation_outbox (
                command_id TEXT PRIMARY KEY,
                mission_id TEXT NOT NULL UNIQUE REFERENCES missions(id),
                organization_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                profile TEXT NOT NULL,
                intent_digest TEXT NOT NULL,
                mission_version INTEGER NOT NULL,
                centurion_grant_id TEXT NOT NULL,
                scout_grant_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('PENDING', 'DELIVERED', 'BLOCKED')),
                intake_id TEXT,
                last_error_code TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00Z',
                updated_at TEXT NOT NULL
            )"""
        )
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(investigation_outbox)")}
        if "attempt_count" not in columns:
            self.connection.execute(
                "ALTER TABLE investigation_outbox ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0"
            )
        if "next_attempt_at" not in columns:
            self.connection.execute(
                "ALTER TABLE investigation_outbox ADD COLUMN next_attempt_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00Z'"
            )

    def get_by_command(self, command_id: str) -> InvestigationIntent | None:
        row = self.connection.execute(
            "SELECT * FROM investigation_outbox WHERE command_id = ?", (command_id,)
        ).fetchone()
        return self._intent(row) if row else None

    def get_by_mission(self, mission_id: str) -> InvestigationIntent | None:
        row = self.connection.execute(
            "SELECT * FROM investigation_outbox WHERE mission_id = ?", (mission_id,)
        ).fetchone()
        return self._intent(row) if row else None

    def pending(self, limit: int = 16) -> tuple[InvestigationIntent, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("INVALID_OUTBOX_LIMIT")
        rows = self.connection.execute(
            "SELECT * FROM investigation_outbox WHERE status = 'PENDING' AND next_attempt_at <= ? "
            "ORDER BY next_attempt_at, command_id LIMIT ?",
            (_now(), limit),
        ).fetchall()
        return tuple(self._intent(row) for row in rows)

    def insert(self, intent: InvestigationIntent) -> None:
        self.connection.execute(
            """INSERT INTO investigation_outbox
               (command_id, mission_id, organization_id, workspace_id, profile,
                intent_digest, mission_version, centurion_grant_id, scout_grant_id,
                expires_at, correlation_id, requested_by, status, intake_id,
                last_error_code, attempt_count, next_attempt_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (intent.command_id, intent.mission_id, intent.organization_id,
             intent.workspace_id, intent.profile, intent.intent_digest,
             intent.mission_version, intent.centurion_grant_id,
             intent.scout_grant_id, intent.expires_at, intent.correlation_id,
             intent.requested_by, intent.status, intent.intake_id,
             intent.last_error_code, 0, _now(), _now()),
        )

    def record_error(self, command_id: str, error_code: str, *, retryable: bool = True) -> None:
        if not isinstance(error_code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", error_code):
            raise ValueError("INVALID_DELIVERY_ERROR_CODE")
        row = self.connection.execute(
            "SELECT attempt_count, expires_at FROM investigation_outbox "
            "WHERE command_id = ? AND status = 'PENDING'", (command_id,),
        ).fetchone()
        if row is None:
            return
        attempts = row["attempt_count"] + 1
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        blocked = not retryable or now >= expires
        delay = min(300, 10 * 2 ** min(attempts - 1, 5))
        next_attempt = min(now + timedelta(seconds=delay), expires).isoformat().replace("+00:00", "Z")
        self.connection.execute(
            """UPDATE investigation_outbox
               SET status = ?, last_error_code = ?, attempt_count = ?,
                   next_attempt_at = ?, updated_at = ?
               WHERE command_id = ? AND status = 'PENDING'""",
            ("BLOCKED" if blocked else "PENDING", error_code, attempts,
             next_attempt, now.isoformat().replace("+00:00", "Z"), command_id),
        )

    def acknowledge(self, command_id: str, intake_id: str) -> InvestigationIntent:
        if not intake_id:
            raise ValueError("INTAKE_ID_REQUIRED")
        row = self.connection.execute(
            "SELECT * FROM investigation_outbox WHERE command_id = ?", (command_id,)
        ).fetchone()
        if row is None:
            raise KeyError(command_id)
        intent = self._intent(row)
        if intent.status == "DELIVERED":
            if intent.intake_id != intake_id:
                raise ValueError("DELIVERY_CONFLICT")
            return intent
        if intent.status != "PENDING":
            raise ValueError("DELIVERY_BLOCKED")
        self.connection.execute(
            """UPDATE investigation_outbox
               SET status = 'DELIVERED', intake_id = ?, last_error_code = NULL,
                   updated_at = ? WHERE command_id = ? AND status = 'PENDING'""",
            (intake_id, _now(), command_id),
        )
        return self._intent(self.connection.execute(
            "SELECT * FROM investigation_outbox WHERE command_id = ?", (command_id,)
        ).fetchone())

    @staticmethod
    def _intent(row: Any) -> InvestigationIntent:
        return InvestigationIntent(**{key: row[key] for key in InvestigationIntent.__dataclass_fields__})
