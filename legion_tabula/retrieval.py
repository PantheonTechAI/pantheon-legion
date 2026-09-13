"""Scoped, provenance-bearing retrieval for the first Tabula slice."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Protocol


@dataclass(frozen=True)
class KnowledgeScope:
    """The organization, workspace, and optional Mission visibility boundary."""

    organization_id: str
    workspace_id: str | None = None
    mission_id: str | None = None

    @classmethod
    def from_mission(cls, mission: object) -> "KnowledgeScope":
        return cls(
            organization_id=mission.organization_id,
            workspace_id=mission.workspace_id,
            mission_id=mission.id,
        )


@dataclass(frozen=True)
class KnowledgeRecord:
    """An immutable knowledge item supplied to Tabula by a trusted ingestion path."""

    id: str
    scope: KnowledgeScope
    source: str
    summary: str
    observed_at: str


@dataclass(frozen=True)
class RetrievedKnowledge:
    """A scoped retrieval result with enough provenance for a Scout evidence item."""

    record_id: str
    source: str
    summary: str
    observed_at: str
    relevance: int


class TabulaRetrievalAdapter(Protocol):
    """Replaceable retrieval contract; a vector store belongs behind this boundary."""

    def retrieve(
        self,
        *,
        scope: KnowledgeScope,
        query: str,
        limit: int = 10,
    ) -> tuple[RetrievedKnowledge, ...]: ...


class InMemoryTabula:
    """Deterministic reference retrieval with strict scope filtering."""

    def __init__(self) -> None:
        self._records: dict[str, KnowledgeRecord] = {}

    def add(self, record: KnowledgeRecord) -> None:
        _validate_record(record)
        if record.id in self._records:
            raise ValueError("KNOWLEDGE_RECORD_DUPLICATE")
        self._records[record.id] = record

    def retrieve(
        self,
        *,
        scope: KnowledgeScope,
        query: str,
        limit: int = 10,
    ) -> tuple[RetrievedKnowledge, ...]:
        if not query.strip() or not 1 <= limit <= 50:
            raise ValueError("KNOWLEDGE_RETRIEVAL_INVALID")
        terms = {term for term in query.lower().split() if term}
        matches = []
        for record in self._records.values():
            if not self._in_scope(record.scope, scope):
                continue
            haystack = f"{record.summary} {record.source}".lower()
            relevance = sum(term in haystack for term in terms)
            if relevance:
                matches.append(
                    RetrievedKnowledge(
                        record_id=record.id,
                        source=record.source,
                        summary=record.summary,
                        observed_at=record.observed_at,
                        relevance=relevance,
                    )
                )
        return tuple(sorted(matches, key=lambda item: (-item.relevance, item.record_id))[:limit])

    @staticmethod
    def _in_scope(record: KnowledgeScope, requested: KnowledgeScope) -> bool:
        if record.organization_id != requested.organization_id:
            return False
        if record.workspace_id is not None and record.workspace_id != requested.workspace_id:
            return False
        return record.mission_id is None or record.mission_id == requested.mission_id


class SQLiteTabula:
    """Durable Tabula retrieval with the same scope and ranking contract.

    This adapter stores trusted ``KnowledgeRecord`` values only. It deliberately
    has no ingestion promotion workflow, embeddings, or vector ranking; those
    remain separate contracts behind ``TabulaRetrievalAdapter``.
    """

    def __init__(self, database: str) -> None:
        self.connection = sqlite3.connect(database)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self.connection.close()

    def add(self, record: KnowledgeRecord) -> None:
        _validate_record(record)
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO knowledge_records (
                        id, organization_id, workspace_id, mission_id, source, summary, observed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.scope.organization_id,
                        record.scope.workspace_id,
                        record.scope.mission_id,
                        record.source,
                        record.summary,
                        record.observed_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("KNOWLEDGE_RECORD_DUPLICATE") from exc

    def retrieve(
        self,
        *,
        scope: KnowledgeScope,
        query: str,
        limit: int = 10,
    ) -> tuple[RetrievedKnowledge, ...]:
        if not query.strip() or not 1 <= limit <= 50:
            raise ValueError("KNOWLEDGE_RETRIEVAL_INVALID")
        terms = {term for term in query.lower().split() if term}
        rows = self.connection.execute(
            """
            SELECT id, source, summary, observed_at
            FROM knowledge_records
            WHERE organization_id = ?
              AND (workspace_id IS NULL OR workspace_id = ?)
              AND (mission_id IS NULL OR mission_id = ?)
            """,
            (scope.organization_id, scope.workspace_id, scope.mission_id),
        )
        matches = []
        for row in rows:
            haystack = f"{row['summary']} {row['source']}".lower()
            relevance = sum(term in haystack for term in terms)
            if relevance:
                matches.append(
                    RetrievedKnowledge(
                        record_id=row["id"],
                        source=row["source"],
                        summary=row["summary"],
                        observed_at=row["observed_at"],
                        relevance=relevance,
                    )
                )
        return tuple(sorted(matches, key=lambda item: (-item.relevance, item.record_id))[:limit])

    def _initialize(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_records (
                    id TEXT PRIMARY KEY,
                    organization_id TEXT NOT NULL,
                    workspace_id TEXT,
                    mission_id TEXT,
                    source TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                )
                """
            )


def _validate_record(record: KnowledgeRecord) -> None:
    if not record.id or not record.scope.organization_id:
        raise ValueError("KNOWLEDGE_RECORD_INVALID")
    if not record.source or not record.summary or not record.observed_at:
        raise ValueError("KNOWLEDGE_RECORD_INVALID")
