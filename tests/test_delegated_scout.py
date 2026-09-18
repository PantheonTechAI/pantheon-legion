import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from legion_kernel import Principal, PrincipalType
from legion_runtime import (
    AgentRole,
    AttemptStatus,
    AssignmentStatus,
    AuthorityUnavailable,
    MissionAuthorityView,
    NextIntent,
    PersistentAgentRuntime,
    RuntimeOperationError,
    WorkStatus,
)
from legion_runtime.cognition import AgentCognitionResult
from legion_runtime.mission_context import AuthorizedMissionContext
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
MISSION = "33333333-3333-4333-8333-333333333333"
CORRELATION = "44444444-4444-4444-8444-444444444444"


class FakeAuthority:
    def _view(self, mission_id=MISSION):
        return MissionAuthorityView(
            mission_id=mission_id,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_status="ACTIVE",
            mission_version=3,
            roe_revision=2,
            decision_id="agent-decision",
            policy_version="test-1",
            evaluated_at="2026-09-18T00:00:00Z",
        )

    def authorize_assignment(self, **kwargs):
        return self._view(kwargs["mission_id"])

    def authorize_resume(self, **kwargs):
        return self._view(kwargs["mission_id"])


class FakeMissionContext:
    def __init__(self):
        self.calls = []
        self.error = None

    def authorize_and_read(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return AuthorizedMissionContext(
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_id=MISSION,
            mission_version=4,
            mission_status="ACTIVE",
            title="Bounded mission",
            objective="Establish durable coordination",
            roe_level="SUPERVISED",
            constraints=("Read only",),
            authorization_decision_id="context-decision",
            policy_version="test-2",
            roe_revision=2,
            evaluated_at="2026-09-18T00:01:00Z",
        )


class RecordingCognition:
    def __init__(self):
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        return AgentCognitionResult(
            request_id=request.request_id,
            agent_id=request.agent_id,
            work_item_id=request.work_item_id,
            attempt_id=request.attempt_id,
            mission_id=request.mission_id,
            mission_version=request.mission_version,
            summary="Bounded Scout result",
            evidence_references=("evidence:one",),
        )


class BlockingCognition(RecordingCognition):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, request):
        self.requests.append(request)
        self.started.set()
        if not self.release.wait(timeout=10):
            raise TimeoutError("test cognition was not released")
        return AgentCognitionResult(
            request_id=request.request_id,
            agent_id=request.agent_id,
            work_item_id=request.work_item_id,
            attempt_id=request.attempt_id,
            mission_id=request.mission_id,
            mission_version=request.mission_version,
            summary="Late result",
        )


class DelegatedScoutTests(unittest.TestCase):
    def setUp(self):
        reset_runtime_database()
        self.authority = FakeAuthority()
        self.context = FakeMissionContext()
        self.cognition = RecordingCognition()
        self.owner = Principal(
            PrincipalType.HUMAN,
            "owner",
            frozenset({"MISSION_OWNER", "OPERATOR"}),
        )
        self.runtime = self._runtime()
        self.centurion, self.centurion_assignment, self.centurion_binding = (
            self._create_assigned_agent("centurion")
        )
        self.scout, self.scout_assignment, self.scout_binding = (
            self._create_assigned_agent("scout")
        )

    def tearDown(self):
        self.runtime.close()

    def _runtime(self, cognition=None):
        return PersistentAgentRuntime(
            new_runtime_store(),
            self.authority,
            mission_context=self.context,
            cognition=cognition or self.cognition,
        )

    def _create_assigned_agent(self, role):
        create = (
            self.runtime.create_centurion
            if role == "centurion"
            else self.runtime.create_scout
        )
        agent = create(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name=role.title(),
            idempotency_key=f"create-{role}",
        )
        assignment = self.runtime.request_assignment(
            actor=self.owner,
            agent_id=agent.agent_id,
            mission_id=MISSION,
            correlation_id=CORRELATION,
            idempotency_key=f"assign-{role}",
        )
        resumed = self.runtime.resume_assignment(
            assignment_id=assignment.assignment_id,
            workload=Principal(PrincipalType.WORKLOAD, f"{role}-workload-a"),
            delegation_id=f"{role}-grant-a",
            correlation_id=CORRELATION,
            idempotency_key=f"resume-{role}-a",
        )
        return agent, assignment, resumed.binding

    def _delegate(self):
        return self.runtime.delegate_work(
            centurion_binding_id=self.centurion_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "centurion-workload-a"),
            scout_assignment_id=self.scout_assignment.assignment_id,
            objective="Inspect the bounded Mission context",
            required_capabilities=("read_only_analysis",),
            correlation_id=CORRELATION,
            idempotency_key="delegate-one",
        )

    def test_full_cycle_survives_scout_binding_replacement(self):
        self.assertEqual(self.scout.role, AgentRole.SCOUT)
        self.assertEqual(
            self.runtime.get_checkpoint(self.scout_assignment.assignment_id).next_intent,
            NextIntent.AWAIT_WORK,
        )
        work = self._delegate()
        replacement = self.runtime.resume_assignment(
            assignment_id=self.scout_assignment.assignment_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-b"),
            delegation_id="scout-grant-b",
            correlation_id="55555555-5555-4555-8555-555555555555",
            idempotency_key="resume-scout-b",
        )
        self.assertEqual(replacement.agent.agent_id, self.scout.agent_id)
        self.assertEqual(replacement.checkpoint.next_intent, NextIntent.EXECUTE_WORK)
        self.assertEqual(replacement.checkpoint.focus_work_item_id, work.work_item_id)

        attempt = self.runtime.claim_work(
            work_item_id=work.work_item_id,
            scout_binding_id=replacement.binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-b"),
            idempotency_key="claim-one",
        )
        replay = self.runtime.claim_work(
            work_item_id=work.work_item_id,
            scout_binding_id=replacement.binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-b"),
            idempotency_key="claim-one",
        )
        self.assertEqual(replay.attempt_id, attempt.attempt_id)

        result = self.runtime.execute_scout_work(
            work_item_id=work.work_item_id,
            scout_binding_id=replacement.binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-b"),
            idempotency_key="execute-one",
        )
        self.assertEqual(result.summary, "Bounded Scout result")
        self.assertEqual(
            self.runtime.get_work_item(work.work_item_id).status,
            WorkStatus.COMPLETED,
        )
        self.assertEqual(
            self.runtime.get_checkpoint(self.scout_assignment.assignment_id).next_intent,
            NextIntent.AWAIT_WORK,
        )
        self.assertEqual(
            self.runtime.get_checkpoint(
                self.centurion_assignment.assignment_id
            ).next_intent,
            NextIntent.ASSESS_WORK_RESULT,
        )
        self.assertEqual(len(self.context.calls), 1)
        request = self.cognition.requests[0]
        self.assertEqual(request.agent_id, self.scout.agent_id)
        self.assertEqual(request.workload_subject, "scout-workload-b")
        self.assertEqual(request.work_item_id, work.work_item_id)
        events = self.runtime.list_events(self.scout.agent_id)
        self.assertTrue(all("Bounded Scout result" not in str(event.data) for event in events))

        self.runtime.close()
        self.runtime = self._runtime()
        self.assertEqual(
            self.runtime.get_work_result(work.work_item_id).result_id,
            result.result_id,
        )

    def test_authority_unavailable_prevents_cognition_and_is_retryable(self):
        work = self._delegate()
        attempt = self.runtime.claim_work(
            work_item_id=work.work_item_id,
            scout_binding_id=self.scout_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-a"),
            idempotency_key="claim-one",
        )
        self.context.error = AuthorityUnavailable()
        with self.assertRaisesRegex(RuntimeOperationError, "AUTHORITY_UNAVAILABLE"):
            self.runtime.execute_scout_work(
                work_item_id=work.work_item_id,
                scout_binding_id=self.scout_binding.binding_id,
                workload=Principal(PrincipalType.WORKLOAD, "scout-workload-a"),
                idempotency_key="execute-one",
            )
        self.assertEqual(self.cognition.requests, [])
        self.assertEqual(
            self.runtime.get_work_item(work.work_item_id).status,
            WorkStatus.RETRYABLE,
        )
        stored = self.runtime.repository.get_work_attempt(attempt.attempt_id)
        self.assertEqual(stored.error_code, "AUTHORITY_UNAVAILABLE")

    def test_wrong_workload_cannot_claim(self):
        work = self._delegate()
        with self.assertRaisesRegex(RuntimeOperationError, "WORKLOAD_BINDING_MISMATCH"):
            self.runtime.claim_work(
                work_item_id=work.work_item_id,
                scout_binding_id=self.scout_binding.binding_id,
                workload=Principal(PrincipalType.WORKLOAD, "wrong-workload"),
                idempotency_key="wrong-claim",
            )
        self.assertEqual(
            self.runtime.get_work_item(work.work_item_id).status,
            WorkStatus.QUEUED,
        )

    def test_late_cognition_result_cannot_revive_cancelled_work(self):
        work = self._delegate()
        self.runtime.claim_work(
            work_item_id=work.work_item_id,
            scout_binding_id=self.scout_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-a"),
            idempotency_key="claim-one",
        )
        blocking = BlockingCognition()

        def execute():
            runtime = self._runtime(blocking)
            try:
                return runtime.execute_scout_work(
                    work_item_id=work.work_item_id,
                    scout_binding_id=self.scout_binding.binding_id,
                    workload=Principal(PrincipalType.WORKLOAD, "scout-workload-a"),
                    idempotency_key="execute-one",
                )
            finally:
                runtime.close()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(execute)
            self.assertTrue(blocking.started.wait(timeout=10))
            cancelled = self.runtime.cancel_work(
                work_item_id=work.work_item_id,
                centurion_binding_id=self.centurion_binding.binding_id,
                workload=Principal(PrincipalType.WORKLOAD, "centurion-workload-a"),
                reason="Objective superseded",
                idempotency_key="cancel-one",
            )
            blocking.release.set()
            with self.assertRaisesRegex(RuntimeOperationError, "WORK_CANCELLED"):
                future.result(timeout=10)
        self.assertEqual(cancelled.status, WorkStatus.CANCELLED)
        self.assertIsNone(self.runtime.get_work_result(work.work_item_id))
        self.assertEqual(
            self.runtime.get_work_item(work.work_item_id).status,
            WorkStatus.CANCELLED,
        )


    def test_concurrent_claims_create_one_attempt(self):
        work = self._delegate()

        def claim(suffix):
            runtime = self._runtime()
            try:
                return runtime.claim_work(
                    work_item_id=work.work_item_id,
                    scout_binding_id=self.scout_binding.binding_id,
                    workload=Principal(PrincipalType.WORKLOAD, "scout-workload-a"),
                    idempotency_key=f"claim-{suffix}",
                )
            except RuntimeOperationError as exc:
                return exc.code
            finally:
                runtime.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(claim, ("a", "b")))
        attempts = self.runtime.repository.list_work_attempts(work.work_item_id)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(outcomes.count("WORK_NOT_CLAIMABLE"), 1)

    def test_running_attempt_reconciles_as_ambiguous_then_retries(self):
        work = self._delegate()
        attempt = self.runtime.claim_work(
            work_item_id=work.work_item_id,
            scout_binding_id=self.scout_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-a"),
            idempotency_key="claim-one",
        )
        with self.runtime.repository.transaction(
            lock_keys=self.runtime._work_lock_keys(work)
        ):
            self.runtime.repository.save_work_attempt(
                replace(
                    attempt,
                    status=AttemptStatus.RUNNING,
                    mission_version=4,
                    authorization_decision_id="ambiguous-decision",
                    version=2,
                    updated_at="2026-09-18T00:02:00Z",
                ),
                expected_previous_version=1,
            )
        self.runtime.close()
        self.runtime = self._runtime()
        reconciled = self.runtime.reconcile_work(
            work_item_id=work.work_item_id,
            scout_binding_id=self.scout_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-a"),
            idempotency_key="reconcile-one",
        )
        self.assertEqual(reconciled.status, WorkStatus.RETRYABLE)
        abandoned = self.runtime.repository.get_work_attempt(attempt.attempt_id)
        self.assertEqual(abandoned.status, AttemptStatus.ABANDONED)
        self.assertEqual(abandoned.error_code, "AMBIGUOUS_COGNITION_OUTCOME")
        retry = self.runtime.claim_work(
            work_item_id=work.work_item_id,
            scout_binding_id=self.scout_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-a"),
            idempotency_key="claim-two",
        )
        self.assertEqual(retry.attempt_number, 2)

    def test_delegate_replay_rejects_changed_input(self):
        work = self._delegate()
        replay = self._delegate()
        self.assertEqual(replay.work_item_id, work.work_item_id)
        with self.assertRaisesRegex(RuntimeOperationError, "IDEMPOTENCY_KEY_REUSE"):
            self.runtime.delegate_work(
                centurion_binding_id=self.centurion_binding.binding_id,
                workload=Principal(PrincipalType.WORKLOAD, "centurion-workload-a"),
                scout_assignment_id=self.scout_assignment.assignment_id,
                objective="Changed objective",
                required_capabilities=("read_only_analysis",),
                correlation_id=CORRELATION,
                idempotency_key="delegate-one",
            )


    def test_cross_mission_delegation_fails_without_partial_state(self):
        other_mission = "99999999-9999-4999-8999-999999999999"
        other_scout = self.runtime.create_scout(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="Other Scout",
            idempotency_key="create-other-scout",
        )
        other_assignment = self.runtime.request_assignment(
            actor=self.owner,
            agent_id=other_scout.agent_id,
            mission_id=other_mission,
            correlation_id=CORRELATION,
            idempotency_key="assign-other-scout",
        )
        self.assertEqual(other_assignment.status, AssignmentStatus.ASSIGNED)
        with self.assertRaisesRegex(RuntimeOperationError, "WORK_SCOPE_MISMATCH"):
            self.runtime.delegate_work(
                centurion_binding_id=self.centurion_binding.binding_id,
                workload=Principal(
                    PrincipalType.WORKLOAD, "centurion-workload-a"
                ),
                scout_assignment_id=other_assignment.assignment_id,
                objective="Cross-Mission work must fail",
                required_capabilities=("read_only_analysis",),
                correlation_id=CORRELATION,
                idempotency_key="cross-mission",
            )
        self.assertEqual(
            self.runtime.list_work_for_assignment(other_assignment.assignment_id), []
        )

    def test_delegate_racing_scout_resume_preserves_event_sequences_and_focus(self):
        replacement_workload = Principal(
            PrincipalType.WORKLOAD, "scout-workload-b"
        )

        def delegate():
            runtime = self._runtime()
            try:
                return runtime.delegate_work(
                    centurion_binding_id=self.centurion_binding.binding_id,
                    workload=Principal(
                        PrincipalType.WORKLOAD, "centurion-workload-a"
                    ),
                    scout_assignment_id=self.scout_assignment.assignment_id,
                    objective="Race-safe work",
                    required_capabilities=("read_only_analysis",),
                    correlation_id=CORRELATION,
                    idempotency_key="race-delegate",
                )
            finally:
                runtime.close()

        def resume():
            runtime = self._runtime()
            try:
                return runtime.resume_assignment(
                    assignment_id=self.scout_assignment.assignment_id,
                    workload=replacement_workload,
                    delegation_id="scout-grant-b",
                    correlation_id="55555555-5555-4555-8555-555555555555",
                    idempotency_key="race-resume",
                )
            finally:
                runtime.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            delegated_future = executor.submit(delegate)
            resumed_future = executor.submit(resume)
            work = delegated_future.result(timeout=10)
            resumed = resumed_future.result(timeout=10)
        checkpoint = self.runtime.get_checkpoint(self.scout_assignment.assignment_id)
        self.assertEqual(checkpoint.next_intent, NextIntent.EXECUTE_WORK)
        self.assertEqual(checkpoint.focus_work_item_id, work.work_item_id)
        self.assertEqual(resumed.agent.agent_id, self.scout.agent_id)
        events = self.runtime.list_events(self.scout.agent_id)
        self.assertEqual(
            [event.sequence for event in events],
            list(range(1, len(events) + 1)),
        )
        self.assertEqual(
            len({event.sequence for event in events}),
            len(events),
        )

    def test_concurrent_execute_accepts_one_result(self):
        work = self._delegate()
        self.runtime.claim_work(
            work_item_id=work.work_item_id,
            scout_binding_id=self.scout_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload-a"),
            idempotency_key="claim-one",
        )

        def execute(suffix):
            runtime = self._runtime()
            try:
                return runtime.execute_scout_work(
                    work_item_id=work.work_item_id,
                    scout_binding_id=self.scout_binding.binding_id,
                    workload=Principal(
                        PrincipalType.WORKLOAD, "scout-workload-a"
                    ),
                    idempotency_key=f"execute-{suffix}",
                )
            except RuntimeOperationError as exc:
                return exc.code
            finally:
                runtime.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(execute, ("a", "b")))
        results = [value for value in outcomes if not isinstance(value, str)]
        self.assertEqual(len(results), 1)
        losing_codes = {
            value for value in outcomes if isinstance(value, str)
        }
        self.assertEqual(len(losing_codes), 1)
        self.assertTrue(losing_codes <= {"WORK_RECONCILIATION_REQUIRED", "WORK_NOT_CLAIMED"})
        stored = self.runtime.get_work_result(work.work_item_id)
        self.assertEqual(stored.result_id, results[0].result_id)
        self.assertEqual(
            self.runtime.get_work_item(work.work_item_id).status,
            WorkStatus.COMPLETED,
        )
        self.assertEqual(len(self.cognition.requests), 1)
if __name__ == "__main__":
    unittest.main()
