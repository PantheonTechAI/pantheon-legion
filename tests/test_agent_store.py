import unittest
from dataclasses import replace
from unittest import mock

from legion_runtime import (
    ActorRef,
    AgentIdentity,
    AgentRole,
    AgentStatus,
    AgentStoreConflict,
    DuplicateRuntimeEvent,
    PostgreSQLAgentStore,
    RuntimeEvent,
)
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


class PostgreSQLAgentStoreTests(unittest.TestCase):
    def setUp(self):
        reset_runtime_database()
        self.store = new_runtime_store()
        self.agent = AgentIdentity(
            agent_id="11111111-1111-4111-8111-111111111111",
            organization_id="22222222-2222-4222-8222-222222222222",
            workspace_id="33333333-3333-4333-8333-333333333333",
            display_name="First Centurion",
            role=AgentRole.CENTURION,
            status=AgentStatus.ACTIVE,
            version=1,
            created_by=ActorRef("HUMAN", "owner"),
            created_at="2026-09-17T00:00:00Z",
            updated_at="2026-09-17T00:00:00Z",
        )

    def tearDown(self):
        self.store.close()

    def test_agent_and_event_survive_repository_reconstruction(self):
        event = RuntimeEvent(
            event_id="44444444-4444-4444-8444-444444444444",
            sequence=1,
            event_type="AgentCreated",
            occurred_at="2026-09-17T00:00:00Z",
            agent_id=self.agent.agent_id,
            actor=self.agent.created_by,
            result="SUCCESS",
            correlation_id="55555555-5555-4555-8555-555555555555",
        )
        with self.store.transaction(lock_key=f"agent:{self.agent.agent_id}"):
            self.store.save_agent(self.agent, expected_previous_version=None)
            self.store.append_event(event)
        self.store.close()
        reopened = new_runtime_store()
        self.assertEqual(reopened.get_agent(self.agent.agent_id), self.agent)
        self.assertEqual(reopened.list_events(self.agent.agent_id), [event])
        reopened.close()
        self.store = new_runtime_store()

    def test_compare_and_swap_conflict_rolls_back_transaction(self):
        with self.store.transaction(lock_key=f"agent:{self.agent.agent_id}"):
            self.store.save_agent(self.agent, expected_previous_version=None)
        updated = replace(
            self.agent,
            display_name="Updated",
            version=2,
            updated_at="2026-09-17T00:01:00Z",
        )
        with self.store.transaction(lock_key=f"agent:{self.agent.agent_id}"):
            self.store.save_agent(updated, expected_previous_version=1)
        with self.assertRaises(AgentStoreConflict):
            with self.store.transaction(lock_key=f"agent:{self.agent.agent_id}"):
                self.store.save_agent(
                    replace(updated, display_name="Stale", version=3),
                    expected_previous_version=1,
                )
        self.assertEqual(self.store.get_agent(self.agent.agent_id).display_name, "Updated")

    def test_transaction_rolls_back_state_when_event_append_fails(self):
        with self.assertRaises(DuplicateRuntimeEvent):
            with self.store.transaction(lock_key=f"agent:{self.agent.agent_id}"):
                self.store.save_agent(self.agent, expected_previous_version=None)
                self.store.append_event(
                    RuntimeEvent(
                        event_id="44444444-4444-4444-8444-444444444444",
                        sequence=1,
                        event_type="AgentCreated",
                        occurred_at="2026-09-17T00:00:00Z",
                        agent_id="99999999-9999-4999-8999-999999999999",
                        actor=self.agent.created_by,
                        result="SUCCESS",
                        correlation_id="55555555-5555-4555-8555-555555555555",
                    )
                )
        self.assertIsNone(self.store.get_agent(self.agent.agent_id))

    def test_event_sequence_cannot_skip(self):
        with self.store.transaction(lock_key=f"agent:{self.agent.agent_id}"):
            self.store.save_agent(self.agent, expected_previous_version=None)
        skipped = RuntimeEvent(
            event_id="44444444-4444-4444-8444-444444444444",
            sequence=2,
            event_type="AgentAssigned",
            occurred_at="2026-09-17T00:00:00Z",
            agent_id=self.agent.agent_id,
            actor=self.agent.created_by,
            result="SUCCESS",
            correlation_id="55555555-5555-4555-8555-555555555555",
        )
        with self.assertRaises(DuplicateRuntimeEvent):
            with self.store.transaction(lock_key=f"agent:{self.agent.agent_id}"):
                self.store.append_event(skipped)
        self.assertEqual(self.store.list_events(self.agent.agent_id), [])

    def test_writes_outside_transaction_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "writes require transaction"):
            self.store.save_agent(self.agent, expected_previous_version=None)

    @mock.patch("legion_runtime.postgres.create_engine")
    def test_constructor_does_not_create_or_migrate_schema(self, create_engine):
        engine = mock.Mock()
        create_engine.return_value = engine
        store = PostgreSQLAgentStore("postgresql+psycopg://ignored/ignored")
        create_engine.assert_called_once()
        engine.connect.assert_not_called()
        store.close()


if __name__ == "__main__":
    unittest.main()
