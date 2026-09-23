import json
import os
import unittest
from unittest import mock

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.runtime_postgres import reset_runtime_database, runtime_test_database_url


class GroundedScoutMigrationTests(unittest.TestCase):
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

    def _insert_phase2_work(self):
        engine = create_engine(self.url, future=True)
        values = {
            "centurion": "11111111-1111-4111-8111-111111111111",
            "scout": "22222222-2222-4222-8222-222222222222",
            "centurion_assignment": "33333333-3333-4333-8333-333333333333",
            "scout_assignment": "44444444-4444-4444-8444-444444444444",
            "mission": "55555555-5555-4555-8555-555555555555",
            "work": "66666666-6666-4666-8666-666666666666",
            "correlation": "77777777-7777-4777-8777-777777777777",
            "timestamp": "2026-09-18T00:00:00Z",
        }
        with engine.begin() as connection:
            for agent_id, role in (
                (values["centurion"], "CENTURION"),
                (values["scout"], "SCOUT"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO agents "
                        "(agent_id, organization_id, workspace_id, display_name, "
                        "role, status, version, created_by_type, created_by_subject, "
                        "created_at, updated_at) VALUES "
                        "(:agent_id, '88888888-8888-4888-8888-888888888888', "
                        "'99999999-9999-4999-8999-999999999999', :role, :role, "
                        "'ACTIVE', 1, 'HUMAN', 'owner', :timestamp, :timestamp)"
                    ),
                    {"agent_id": agent_id, "role": role, **values},
                )
            for assignment_id, agent_id in (
                (values["centurion_assignment"], values["centurion"]),
                (values["scout_assignment"], values["scout"]),
            ):
                connection.execute(
                    text(
                        "INSERT INTO mission_assignments "
                        "(assignment_id, agent_id, mission_id, status, mission_version, "
                        "authorization_decision_id, policy_version, requested_by_type, "
                        "requested_by_subject, correlation_id, last_error_code, version, "
                        "created_at, updated_at) VALUES "
                        "(:assignment_id, :agent_id, :mission, 'ASSIGNED', 1, "
                        "'decision', 'policy', 'HUMAN', 'owner', :correlation, NULL, "
                        "1, :timestamp, :timestamp)"
                    ),
                    {
                        "assignment_id": assignment_id,
                        "agent_id": agent_id,
                        **values,
                    },
                )
            connection.execute(
                text(
                    "INSERT INTO runtime_work_items "
                    "(work_item_id, mission_id, centurion_agent_id, "
                    "centurion_assignment_id, scout_agent_id, scout_assignment_id, "
                    "objective, required_capabilities, status, version, correlation_id, "
                    "causation_id, created_at, updated_at, cancelled_at, "
                    "cancellation_reason) VALUES "
                    "(:work, :mission, :centurion, :centurion_assignment, :scout, "
                    ":scout_assignment, 'Legacy read-only work', CAST(:caps AS jsonb), "
                    "'QUEUED', 1, :correlation, NULL, :timestamp, :timestamp, NULL, NULL)"
                ),
                {**values, "caps": json.dumps(["read_only_analysis"])},
            )
        engine.dispose()
        return values

    def test_phase2_rows_upgrade_with_read_only_kind_and_empty_downgrade_is_safe(self):
        with self._environment():
            command.downgrade(self.config, "0002")
            values = self._insert_phase2_work()
            command.upgrade(self.config, "head")
            engine = create_engine(self.url, future=True)
            try:
                with engine.connect() as connection:
                    self.assertEqual(
                        connection.execute(
                            text(
                                "SELECT work_kind FROM runtime_work_items "
                                "WHERE work_item_id = :work"
                            ),
                            values,
                        ).scalar_one(),
                        "READ_ONLY_ANALYSIS",
                    )
                self.assertIn(
                    "runtime_work_evidence_references",
                    inspect(engine).get_table_names(),
                )
            finally:
                engine.dispose()
            command.downgrade(self.config, "0002")
            engine = create_engine(self.url, future=True)
            try:
                columns = {
                    item["name"]
                    for item in inspect(engine).get_columns("runtime_work_items")
                }
                self.assertNotIn("work_kind", columns)
            finally:
                engine.dispose()
            command.upgrade(self.config, "head")

    def test_grounded_data_refuses_downgrade_without_data_loss(self):
        engine = create_engine(self.url, future=True)
        values = None
        with self._environment():
            command.downgrade(self.config, "0002")
            values = self._insert_phase2_work()
            command.upgrade(self.config, "head")
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE runtime_work_items SET work_kind = "
                        "'GROUNDED_CORPUS_ANALYSIS' WHERE work_item_id = :work"
                    ),
                    values,
                )
            with self.assertRaisesRegex(RuntimeError, "cannot downgrade"):
                command.downgrade(self.config, "0002")
        try:
            with engine.connect() as connection:
                self.assertEqual(
                    connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one(),
                    "0005",
                )
                self.assertEqual(
                    connection.execute(
                        text(
                            "SELECT work_kind FROM runtime_work_items "
                            "WHERE work_item_id = :work"
                        ),
                        values,
                    ).scalar_one(),
                    "GROUNDED_CORPUS_ANALYSIS",
                )
        finally:
            engine.dispose()

    def test_metadata_matches_head(self):
        with self._environment():
            command.check(self.config)


if __name__ == "__main__":
    unittest.main()
