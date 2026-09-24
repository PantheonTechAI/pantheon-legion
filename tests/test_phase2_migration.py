import os
import unittest
from unittest import mock

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from legion_runtime import ActorRef, AgentIdentity, AgentRole, AgentStatus
from tests.runtime_postgres import (
    new_runtime_store,
    reset_runtime_database,
    runtime_test_database_url,
)


class Phase2MigrationTests(unittest.TestCase):
    def setUp(self):
        reset_runtime_database()
        self.url = runtime_test_database_url()
        self.config = Config("legion_runtime/alembic.ini")

    def _environment(self):
        return mock.patch.dict(
            os.environ,
            {"LEGION_RUNTIME_DATABASE_URL": self.url},
            clear=False,
        )

    def test_empty_phase2_schema_round_trips(self):
        with self._environment():
            command.downgrade(self.config, "0001")
            engine = create_engine(self.url, future=True)
            try:
                tables = set(inspect(engine).get_table_names())
                self.assertNotIn("runtime_work_items", tables)
                self.assertNotIn("runtime_work_attempts", tables)
                self.assertNotIn("runtime_work_results", tables)
            finally:
                engine.dispose()
            command.upgrade(self.config, "head")

    def test_populated_phase2_downgrade_refuses_without_data_loss(self):
        store = new_runtime_store()
        scout = AgentIdentity(
            agent_id="11111111-1111-4111-8111-111111111111",
            organization_id="22222222-2222-4222-8222-222222222222",
            workspace_id="33333333-3333-4333-8333-333333333333",
            display_name="Persistent Scout",
            role=AgentRole.SCOUT,
            status=AgentStatus.ACTIVE,
            version=1,
            created_by=ActorRef("HUMAN", "owner"),
            created_at="2026-09-18T00:00:00Z",
            updated_at="2026-09-18T00:00:00Z",
        )
        with store.transaction(
            lock_key=(
                "organization:22222222-2222-4222-8222-222222222222:"
                "workspace:33333333-3333-4333-8333-333333333333"
            )
        ):
            store.save_agent(scout, expected_previous_version=None)
        store.close()

        with self._environment():
            with self.assertRaisesRegex(RuntimeError, "cannot downgrade"):
                command.downgrade(self.config, "0001")
        engine = create_engine(self.url, future=True)
        try:
            tables = set(inspect(engine).get_table_names())
            self.assertIn("runtime_work_items", tables)
            with engine.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        text("SELECT role FROM agents WHERE agent_id = :agent_id"),
                        {"agent_id": scout.agent_id},
                    ).scalar_one(),
                    "SCOUT",
                )
                self.assertEqual(
                    connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one(),
                    "0006",
                )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
