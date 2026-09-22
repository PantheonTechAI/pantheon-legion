"""Guarded PostgreSQL helpers for Phase 1 integration and acceptance tests."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from legion_runtime import PostgreSQLAgentStore


RUNTIME_TABLES = {
    "cognition_turns",
    "agents",
    "mission_assignments",
    "coordination_checkpoints",
    "runtime_bindings",
    "runtime_events",
    "runtime_idempotency",
    "runtime_work_attempts",
    "runtime_work_evidence_references",
    "runtime_work_items",
    "runtime_work_results",
}


def runtime_test_database_url() -> str:
    value = os.environ.get("LEGION_RUNTIME_TEST_DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError(
            "LEGION_RUNTIME_TEST_DATABASE_URL is required for Phase 1 PostgreSQL tests"
        )
    parsed = make_url(value)
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("Runtime persistence tests require PostgreSQL")
    if not parsed.database or not parsed.database.endswith("_test"):
        raise RuntimeError(
            "refusing destructive reset: Runtime test database must end with '_test'"
        )
    deployed = os.environ.get("LEGION_RUNTIME_DATABASE_URL", "").strip()
    if deployed and _database_target(make_url(deployed)) == _database_target(parsed):
        raise RuntimeError(
            "refusing destructive reset: deployed and test database targets match"
        )
    return value


def _database_target(url) -> tuple[str, str | None, int, str | None]:
    return (
        url.get_backend_name(),
        url.host,
        url.port or 5432,
        url.database,
    )


def reset_runtime_database() -> None:
    engine = create_engine(runtime_test_database_url(), future=True)
    try:
        tables = set(inspect(engine).get_table_names())
        missing = RUNTIME_TABLES - tables
        if missing:
            raise RuntimeError(
                "Runtime migrations are not current; missing tables: "
                + ", ".join(sorted(missing))
            )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "TRUNCATE TABLE runtime_work_results, "
                    "runtime_work_evidence_references, runtime_work_attempts, "
                    "runtime_work_items, runtime_events, runtime_bindings, "
                    "coordination_checkpoints, mission_assignments, "
                    "runtime_idempotency, agents CASCADE"
                )
            )
    finally:
        engine.dispose()


def new_runtime_store() -> PostgreSQLAgentStore:
    return PostgreSQLAgentStore(runtime_test_database_url())


def runtime_table_names(store: PostgreSQLAgentStore) -> set[str]:
    return set(inspect(store.engine).get_table_names())
