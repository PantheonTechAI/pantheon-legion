import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from sqlalchemy import func, select

from legion_kernel import Principal, PrincipalType
from legion_runtime import (
    AssignmentStatus,
    AuthorityDenied,
    AuthorityUnavailable,
    BindingStatus,
    CheckpointState,
    MissionAuthorityView,
    PersistentAgentRuntime,
    RuntimeOperationError,
)
from legion_runtime.database import mission_assignments
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
MISSION = "33333333-3333-4333-8333-333333333333"
CORRELATION = "44444444-4444-4444-8444-444444444444"


class FakeAuthority:
    def __init__(self):
        self.assignment_error = None
        self.resume_error = None
        self.workspace_id = WORKSPACE

    def _view(self):
        return MissionAuthorityView(
            mission_id=MISSION,
            organization_id=ORG,
            workspace_id=self.workspace_id,
            mission_status="ACTIVE",
            mission_version=2,
            roe_revision=1,
            decision_id="decision",
            policy_version="test-1",
            evaluated_at="2026-09-17T00:00:00Z",
        )

    def authorize_assignment(self, **kwargs):
        if self.assignment_error:
            raise self.assignment_error
        return self._view()

    def authorize_resume(self, **kwargs):
        if self.resume_error:
            raise self.resume_error
        return self._view()


class PersistentAgentRuntimeTests(unittest.TestCase):
    def setUp(self):
        reset_runtime_database()
        self.authority = FakeAuthority()
        self.owner = Principal(
            PrincipalType.HUMAN,
            "owner",
            frozenset({"MISSION_OWNER", "OPERATOR"}),
        )
        self.runtime = PersistentAgentRuntime(new_runtime_store(), self.authority)

    def tearDown(self):
        self.runtime.close()

    def create_and_assign(self):
        agent = self.runtime.create_centurion(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="First Centurion",
            idempotency_key="create-one",
        )
        assignment = self.runtime.request_assignment(
            actor=self.owner,
            agent_id=agent.agent_id,
            mission_id=MISSION,
            correlation_id=CORRELATION,
            idempotency_key="assign-one",
        )
        return agent, assignment

    def test_create_assign_and_replay_are_idempotent(self):
        agent, assignment = self.create_and_assign()
        replayed_agent = self.runtime.create_centurion(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="First Centurion",
            idempotency_key="create-one",
        )
        replayed_assignment = self.runtime.request_assignment(
            actor=self.owner,
            agent_id=agent.agent_id,
            mission_id=MISSION,
            correlation_id=CORRELATION,
            idempotency_key="assign-one",
        )
        self.assertEqual(replayed_agent.agent_id, agent.agent_id)
        self.assertEqual(replayed_assignment.assignment_id, assignment.assignment_id)
        self.assertEqual(assignment.status, AssignmentStatus.ASSIGNED)
        self.assertEqual(
            self.runtime.get_checkpoint(assignment.assignment_id).state,
            CheckpointState.READY,
        )
        self.assertEqual(
            [event.event_type for event in self.runtime.list_events(agent.agent_id)],
            ["AgentCreated", "AgentAssignmentRequested", "AgentAssigned"],
        )
        with self.assertRaisesRegex(RuntimeOperationError, "IDEMPOTENCY_KEY_REUSE"):
            self.runtime.create_centurion(
                actor=self.owner,
                organization_id=ORG,
                workspace_id=WORKSPACE,
                display_name="Different Centurion",
                idempotency_key="create-one",
            )
        with self.assertRaisesRegex(RuntimeOperationError, "IDEMPOTENCY_KEY_REUSE"):
            self.runtime.request_assignment(
                actor=self.owner,
                agent_id=agent.agent_id,
                mission_id="99999999-9999-4999-8999-999999999999",
                correlation_id=CORRELATION,
                idempotency_key="assign-one",
            )

    def test_unavailable_assignment_is_durable_and_explicitly_reconciles(self):
        self.authority.assignment_error = AuthorityUnavailable()
        agent = self.runtime.create_centurion(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="First Centurion",
            idempotency_key="create-one",
        )
        blocked = self.runtime.request_assignment(
            actor=self.owner,
            agent_id=agent.agent_id,
            mission_id=MISSION,
            correlation_id=CORRELATION,
            idempotency_key="assign-one",
        )
        self.assertEqual(blocked.status, AssignmentStatus.BLOCKED)
        with self.assertRaisesRegex(RuntimeOperationError, "ASSIGNMENT_NOT_AUTHORIZED"):
            self.runtime.resume_assignment(
                assignment_id=blocked.assignment_id,
                workload=Principal(PrincipalType.WORKLOAD, "workload-a"),
                delegation_id="read-grant-cannot-authorize-assignment",
                correlation_id="55555555-5555-4555-8555-555555555555",
                idempotency_key="invalid-resume",
            )
        self.runtime.close()
        self.runtime = PersistentAgentRuntime(
            new_runtime_store(), self.authority
        )
        self.assertEqual(
            self.runtime.get_assignment(blocked.assignment_id).status,
            AssignmentStatus.BLOCKED,
        )
        self.authority.assignment_error = None
        assigned = self.runtime.reconcile_assignment(
            assignment_id=blocked.assignment_id,
            actor=self.owner,
            idempotency_key="reconcile-one",
        )
        self.assertEqual(assigned.status, AssignmentStatus.ASSIGNED)
        event_count = len(self.runtime.list_events(agent.agent_id))
        replay = self.runtime.reconcile_assignment(
            assignment_id=blocked.assignment_id,
            actor=self.owner,
            idempotency_key="reconcile-one",
        )
        self.assertEqual(replay.status, AssignmentStatus.ASSIGNED)
        self.assertEqual(len(self.runtime.list_events(agent.agent_id)), event_count)
        with self.assertRaisesRegex(RuntimeOperationError, "IDEMPOTENCY_KEY_REUSE"):
            self.runtime.reconcile_assignment(
                assignment_id=blocked.assignment_id,
                actor=Principal(PrincipalType.HUMAN, "different-owner"),
                idempotency_key="reconcile-one",
            )

    def test_denied_assignment_is_rejected_not_self_authorized(self):
        self.authority.assignment_error = AuthorityDenied("OPERATOR_ROLE_REQUIRED")
        agent = self.runtime.create_centurion(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="First Centurion",
            idempotency_key="create-one",
        )
        assignment = self.runtime.request_assignment(
            actor=self.owner,
            agent_id=agent.agent_id,
            mission_id=MISSION,
            correlation_id=CORRELATION,
            idempotency_key="assign-one",
        )
        self.assertEqual(assignment.status, AssignmentStatus.REJECTED)
        self.assertEqual(assignment.last_error_code, "OPERATOR_ROLE_REQUIRED")

    def test_scope_mismatch_is_rejected_without_rewriting_agent_scope(self):
        self.authority.workspace_id = "99999999-9999-4999-8999-999999999999"
        agent = self.runtime.create_centurion(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="First Centurion",
            idempotency_key="create-one",
        )
        assignment = self.runtime.request_assignment(
            actor=self.owner,
            agent_id=agent.agent_id,
            mission_id=MISSION,
            correlation_id=CORRELATION,
            idempotency_key="assign-one",
        )
        self.assertEqual(assignment.status, AssignmentStatus.REJECTED)
        self.assertEqual(assignment.last_error_code, "SCOPE_MISMATCH")
        self.assertEqual(self.runtime.get_agent(agent.agent_id).workspace_id, WORKSPACE)

    def test_unavailable_resume_blocks_then_fresh_retry_recovers(self):
        agent, assignment = self.create_and_assign()
        self.authority.resume_error = AuthorityUnavailable()
        blocked = self.runtime.resume_assignment(
            assignment_id=assignment.assignment_id,
            workload=Principal(PrincipalType.WORKLOAD, "workload-a"),
            delegation_id="grant-a",
            correlation_id="55555555-5555-4555-8555-555555555555",
            idempotency_key="resume-a",
        )
        self.assertEqual(blocked.assignment.status, AssignmentStatus.BLOCKED)
        self.assertEqual(blocked.binding.status, BindingStatus.BLOCKED)
        self.assertEqual(blocked.checkpoint.next_intent.value, "ASSESS_MISSION")
        self.authority.resume_error = None
        recovered = self.runtime.resume_assignment(
            assignment_id=assignment.assignment_id,
            workload=Principal(PrincipalType.WORKLOAD, "workload-b"),
            delegation_id="grant-b",
            correlation_id="66666666-6666-4666-8666-666666666666",
            idempotency_key="resume-b",
        )
        self.assertEqual(recovered.assignment.status, AssignmentStatus.ASSIGNED)
        self.assertEqual(recovered.binding.status, BindingStatus.ACTIVE)
        self.assertEqual(recovered.agent.agent_id, agent.agent_id)

    def test_concurrent_resume_attempts_leave_one_active_binding(self):
        _, assignment = self.create_and_assign()

        def resume(suffix):
            runtime = PersistentAgentRuntime(
                new_runtime_store(), self.authority
            )
            try:
                return runtime.resume_assignment(
                    assignment_id=assignment.assignment_id,
                    workload=Principal(PrincipalType.WORKLOAD, f"workload-{suffix}"),
                    delegation_id=f"grant-{suffix}",
                    correlation_id=(
                        "77777777-7777-4777-8777-777777777777"
                        if suffix == "a"
                        else "88888888-8888-4888-8888-888888888888"
                    ),
                    idempotency_key=f"resume-{suffix}",
                )
            finally:
                runtime.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(resume, ("a", "b")))
        bindings = self.runtime.list_bindings(assignment.assignment_id)
        self.assertEqual(sum(item.status == BindingStatus.ACTIVE for item in bindings), 1)
        self.assertEqual(
            {item.workload_subject for item in bindings}, {"workload-a", "workload-b"}
        )
        self.assertEqual(
            {result.agent.agent_id for result in results}, {assignment.agent_id}
        )

    def test_concurrent_identical_assignment_requests_create_one_intent(self):
        agent = self.runtime.create_centurion(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="First Centurion",
            idempotency_key="create-one",
        )

        def assign(_):
            runtime = PersistentAgentRuntime(
                new_runtime_store(), self.authority
            )
            try:
                return runtime.request_assignment(
                    actor=self.owner,
                    agent_id=agent.agent_id,
                    mission_id=MISSION,
                    correlation_id=CORRELATION,
                    idempotency_key="assign-one",
                )
            finally:
                runtime.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(assign, (1, 2)))
        self.assertEqual({item.assignment_id for item in results}, {results[0].assignment_id})
        self.assertTrue(all(item.status == AssignmentStatus.ASSIGNED for item in results))
        events = self.runtime.list_events(agent.agent_id)
        self.assertEqual(
            [event.event_type for event in events],
            ["AgentCreated", "AgentAssignmentRequested", "AgentAssigned"],
        )

    def test_concurrent_different_assignment_keys_preserve_one_active_intent(self):
        agent = self.runtime.create_centurion(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="First Centurion",
            idempotency_key="create-one",
        )

        def assign(suffix):
            runtime = PersistentAgentRuntime(
                new_runtime_store(), self.authority
            )
            try:
                assignment = runtime.request_assignment(
                    actor=self.owner,
                    agent_id=agent.agent_id,
                    mission_id=MISSION,
                    correlation_id=CORRELATION,
                    idempotency_key=f"assign-{suffix}",
                )
                return assignment.assignment_id
            except RuntimeOperationError as exc:
                return exc.code
            finally:
                runtime.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(assign, ("a", "b")))
        self.assertEqual(results.count("ACTIVE_ASSIGNMENT_EXISTS"), 1)
        assignment_ids = [
            value for value in results if value != "ACTIVE_ASSIGNMENT_EXISTS"
        ]
        self.assertEqual(len(assignment_ids), 1)
        self.assertEqual(
            self.runtime.get_assignment(assignment_ids[0]).status,
            AssignmentStatus.ASSIGNED,
        )
        with self.runtime.repository.engine.connect() as connection:
            count = connection.execute(
                select(func.count())
                .select_from(mission_assignments)
                .where(mission_assignments.c.agent_id == agent.agent_id)
            ).scalar_one()
        self.assertEqual(count, 1)

    def test_binding_swap_failure_rolls_back_and_same_key_recovers(self):
        _, assignment = self.create_and_assign()
        first = self.runtime.resume_assignment(
            assignment_id=assignment.assignment_id,
            workload=Principal(PrincipalType.WORKLOAD, "workload-a"),
            delegation_id="grant-a",
            correlation_id="55555555-5555-4555-8555-555555555555",
            idempotency_key="resume-a",
        )
        with mock.patch.object(
            self.runtime.repository,
            "save_assignment",
            side_effect=OSError("disk full"),
        ):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.runtime.resume_assignment(
                    assignment_id=assignment.assignment_id,
                    workload=Principal(PrincipalType.WORKLOAD, "workload-b"),
                    delegation_id="grant-b",
                    correlation_id="66666666-6666-4666-8666-666666666666",
                    idempotency_key="resume-b",
                )
        after_failure = self.runtime.list_bindings(assignment.assignment_id)
        self.assertEqual(
            [item.status for item in after_failure],
            [BindingStatus.ACTIVE, BindingStatus.PENDING_AUTHORITY],
        )
        recovered = self.runtime.resume_assignment(
            assignment_id=assignment.assignment_id,
            workload=Principal(PrincipalType.WORKLOAD, "workload-b"),
            delegation_id="grant-b",
            correlation_id="66666666-6666-4666-8666-666666666666",
            idempotency_key="resume-b",
        )
        self.assertEqual(recovered.binding.status, BindingStatus.ACTIVE)
        self.assertEqual(recovered.agent.agent_id, first.agent.agent_id)
        self.assertEqual(
            [item.status for item in self.runtime.list_bindings(assignment.assignment_id)],
            [BindingStatus.RELEASED, BindingStatus.ACTIVE],
        )
        with self.assertRaisesRegex(RuntimeOperationError, "IDEMPOTENCY_KEY_REUSE"):
            self.runtime.resume_assignment(
                assignment_id=assignment.assignment_id,
                workload=Principal(PrincipalType.WORKLOAD, "workload-c"),
                delegation_id="grant-b",
                correlation_id="66666666-6666-4666-8666-666666666666",
                idempotency_key="resume-b",
            )

    def test_new_workload_replaces_binding_but_not_agent_or_checkpoint_intent(self):
        agent, assignment = self.create_and_assign()
        first = self.runtime.resume_assignment(
            assignment_id=assignment.assignment_id,
            workload=Principal(PrincipalType.WORKLOAD, "workload-a"),
            delegation_id="grant-a",
            correlation_id="55555555-5555-4555-8555-555555555555",
            idempotency_key="resume-a",
        )
        first_revision = first.checkpoint.revision
        self.runtime.close()
        self.runtime = PersistentAgentRuntime(
            new_runtime_store(), self.authority
        )
        second = self.runtime.resume_assignment(
            assignment_id=assignment.assignment_id,
            workload=Principal(PrincipalType.WORKLOAD, "workload-b"),
            delegation_id="grant-b",
            correlation_id="66666666-6666-4666-8666-666666666666",
            idempotency_key="resume-b",
        )
        bindings = self.runtime.list_bindings(assignment.assignment_id)
        self.assertEqual(second.agent.agent_id, agent.agent_id)
        self.assertEqual(second.assignment.assignment_id, assignment.assignment_id)
        self.assertEqual(second.checkpoint.next_intent, first.checkpoint.next_intent)
        self.assertGreater(second.checkpoint.revision, first_revision)
        self.assertEqual(
            [(item.workload_subject, item.status) for item in bindings],
            [
                ("workload-a", BindingStatus.RELEASED),
                ("workload-b", BindingStatus.ACTIVE),
            ],
        )


if __name__ == "__main__":
    unittest.main()
