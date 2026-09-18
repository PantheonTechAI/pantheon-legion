import tempfile
import unittest
from pathlib import Path

from aquila_api import InProcessAquilaAgentAuthority, PersistentAquilaService
from legion_kernel import Principal, PrincipalType, RoeLevel
from legion_runtime import AssignmentStatus, BindingStatus, PersistentAgentRuntime
from tests.runtime_postgres import (
    new_runtime_store,
    reset_runtime_database,
    runtime_table_names,
)


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"


class PersistentCenturionAcceptanceTests(unittest.TestCase):
    def test_identity_and_intent_survive_service_and_workload_replacement(self):
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            aquila_database = str(Path(directory) / "aquila.sqlite3")
            owner = Principal(
                PrincipalType.HUMAN,
                "acceptance-owner",
                frozenset({"MISSION_OWNER", "OPERATOR"}),
            )
            workload_a = Principal(PrincipalType.WORKLOAD, "runtime-workload-a")
            workload_b = Principal(PrincipalType.WORKLOAD, "runtime-workload-b")

            aquila = PersistentAquilaService(aquila_database)
            created = aquila.create_mission(
                actor=owner,
                body={
                    "organization_id": ORG,
                    "workspace_id": WORKSPACE,
                    "title": "First persistent Centurion",
                    "objective": "Keep organizational identity across Runtime restart.",
                },
            )
            mission_id = created.body["id"]
            runtime = PersistentAgentRuntime(
                new_runtime_store(),
                InProcessAquilaAgentAuthority(aquila),
            )
            agent = runtime.create_centurion(
                actor=owner,
                organization_id=ORG,
                workspace_id=WORKSPACE,
                display_name="Primus",
                idempotency_key="create-primus",
            )
            assignment = runtime.request_assignment(
                actor=owner,
                agent_id=agent.agent_id,
                mission_id=mission_id,
                correlation_id="33333333-3333-4333-8333-333333333333",
                idempotency_key="assign-primus",
            )
            grant_a = aquila.issue_delegation(
                issuer=owner,
                subject=workload_a,
                mission_id=mission_id,
                allowed_operations=frozenset({"READ_MISSION"}),
                roe_ceiling=RoeLevel.OBSERVE,
                expires_at="9999-01-01T00:00:00Z",
            )
            first = runtime.resume_assignment(
                assignment_id=assignment.assignment_id,
                workload=workload_a,
                delegation_id=grant_a,
                correlation_id="44444444-4444-4444-8444-444444444444",
                idempotency_key="resume-workload-a",
            )
            original_checkpoint_intent = first.checkpoint.next_intent
            original_event_count = len(runtime.list_events(agent.agent_id))
            runtime.close()
            aquila.close()

            aquila = PersistentAquilaService(aquila_database)
            runtime = PersistentAgentRuntime(
                new_runtime_store(),
                InProcessAquilaAgentAuthority(aquila),
            )
            grant_b = aquila.issue_delegation(
                issuer=owner,
                subject=workload_b,
                mission_id=mission_id,
                allowed_operations=frozenset({"READ_MISSION"}),
                roe_ceiling=RoeLevel.OBSERVE,
                expires_at="9999-01-01T00:00:00Z",
            )
            resumed = runtime.resume_assignment(
                assignment_id=assignment.assignment_id,
                workload=workload_b,
                delegation_id=grant_b,
                correlation_id="55555555-5555-4555-8555-555555555555",
                idempotency_key="resume-workload-b",
            )

            self.assertEqual(resumed.agent.agent_id, agent.agent_id)
            self.assertEqual(resumed.assignment.assignment_id, assignment.assignment_id)
            self.assertEqual(resumed.checkpoint.next_intent, original_checkpoint_intent)
            bindings = runtime.list_bindings(assignment.assignment_id)
            self.assertEqual(
                [(binding.workload_subject, binding.status) for binding in bindings],
                [
                    ("runtime-workload-a", BindingStatus.RELEASED),
                    ("runtime-workload-b", BindingStatus.ACTIVE),
                ],
            )
            self.assertEqual(
                len(runtime.list_events(agent.agent_id)), original_event_count + 2
            )
            event_count = len(runtime.list_events(agent.agent_id))
            audit_count = len(aquila.kernel.timeline(mission_id))
            replay = runtime.resume_assignment(
                assignment_id=assignment.assignment_id,
                workload=workload_b,
                delegation_id=grant_b,
                correlation_id="55555555-5555-4555-8555-555555555555",
                idempotency_key="resume-workload-b",
            )
            self.assertEqual(replay.binding.binding_id, resumed.binding.binding_id)
            self.assertEqual(len(runtime.list_events(agent.agent_id)), event_count)
            self.assertEqual(len(aquila.kernel.timeline(mission_id)), audit_count)
            self.assertEqual(aquila.kernel.get_mission(mission_id).version, 1)

            aquila_tables = {
                row[0]
                for row in aquila.store.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            runtime_tables = runtime_table_names(runtime.repository)
            self.assertNotIn("agents", aquila_tables)
            self.assertNotIn("missions", runtime_tables)
            self.assertIn("agents", runtime_tables)
            self.assertTrue(
                any(
                    event.event_type == "AGENT_RUNTIME_AUTHORIZATION_EVALUATED"
                    for event in aquila.kernel.timeline(mission_id)
                )
            )
            runtime.close()
            aquila.close()

    def test_real_aquila_store_failure_blocks_and_fresh_adapter_reconciles(self):
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            aquila_database = str(Path(directory) / "aquila.sqlite3")
            owner = Principal(
                PrincipalType.HUMAN,
                "acceptance-owner",
                frozenset({"MISSION_OWNER", "OPERATOR"}),
            )
            aquila = PersistentAquilaService(aquila_database)
            mission_id = aquila.create_mission(
                actor=owner,
                body={
                    "organization_id": ORG,
                    "workspace_id": WORKSPACE,
                    "title": "Recover authority adapter",
                    "objective": "Fail closed across a real Aquila store outage.",
                },
            ).body["id"]
            runtime = PersistentAgentRuntime(
                new_runtime_store(), InProcessAquilaAgentAuthority(aquila)
            )
            agent = runtime.create_centurion(
                actor=owner,
                organization_id=ORG,
                workspace_id=WORKSPACE,
                display_name="Primus",
                idempotency_key="create-real-outage",
            )

            aquila.close()
            blocked = runtime.request_assignment(
                actor=owner,
                agent_id=agent.agent_id,
                mission_id=mission_id,
                correlation_id="66666666-6666-4666-8666-666666666666",
                idempotency_key="assign-real-outage",
            )
            self.assertEqual(blocked.status, AssignmentStatus.BLOCKED)
            self.assertEqual(blocked.last_error_code, "AUTHORITY_UNAVAILABLE")

            aquila = PersistentAquilaService(aquila_database)
            runtime.authority = InProcessAquilaAgentAuthority(aquila)
            assigned = runtime.reconcile_assignment(
                assignment_id=blocked.assignment_id,
                actor=owner,
                idempotency_key="reconcile-real-outage",
            )
            self.assertEqual(assigned.status, AssignmentStatus.ASSIGNED)
            self.assertIsNone(assigned.last_error_code)
            runtime.close()
            aquila.close()


if __name__ == "__main__":
    unittest.main()
