import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from legion_kernel import Principal, PrincipalType
from legion_runtime import (
    AgentCognitionResult,
    AttemptStage,
    AttemptStatus,
    AuthorityDenied,
    GroundedEvidenceBundle,
    GroundedEvidenceRecord,
    MissionAuthorityView,
    PersistentAgentRuntime,
    RepositoryMissionOrganizationReadModel,
    RuntimeOperationError,
    WorkKind,
    WorkStatus,
)
from legion_runtime.mission_context import AuthorizedMissionContext
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
MISSION = "33333333-3333-4333-8333-333333333333"
CORRELATION = "44444444-4444-4444-8444-444444444444"
AUDIT_CORRELATION = "55555555-5555-4555-8555-555555555555"


class Authority:
    def _view(self, mission_id=MISSION):
        return MissionAuthorityView(
            mission_id=mission_id,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_status="ACTIVE",
            mission_version=3,
            roe_revision=2,
            decision_id="assignment-decision",
            policy_version="test-1",
            evaluated_at="2026-09-18T00:00:00Z",
        )

    def authorize_assignment(self, **kwargs):
        return self._view(kwargs["mission_id"])

    def authorize_resume(self, **kwargs):
        return self._view(kwargs["mission_id"])


class MissionContext:
    def __init__(self):
        self.calls = []

    def authorize_and_read(self, **kwargs):
        self.calls.append(kwargs)
        return AuthorizedMissionContext(
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_id=MISSION,
            mission_version=4,
            mission_status="ACTIVE",
            title="Grounded mission",
            objective="Use organizational evidence",
            roe_level="SUPERVISED",
            constraints=("Read only",),
            authorization_decision_id=f"mission-decision-{len(self.calls)}",
            policy_version="test-2",
            roe_revision=2,
            evaluated_at="2026-09-18T00:01:00Z",
        )


class EvidenceReader:
    def __init__(self):
        self.calls = []
        self.error = None

    def read(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        return GroundedEvidenceBundle(
            authorization_decision_ids=("knowledge-1", "knowledge-2"),
            policy_versions=("policy-1", "policy-1"),
            successful_authorization_decision_id="knowledge-2",
            scope_binding_id="66666666-6666-4666-8666-666666666666",
            scope_binding_version="1.0.0",
            correlation_id=request.correlation_id,
            tabula_audit_correlation_id=AUDIT_CORRELATION,
            retrieved_at="2026-09-18T00:02:00Z",
            records=(
                GroundedEvidenceRecord(
                    record_id="record-one",
                    revision="rev-1",
                    canonical_uri="tabula://corpus/record-one/rev-1",
                    content="sensitive evidence sentinel",
                    retrieved_at="2026-09-18T00:02:00Z",
                ),
                GroundedEvidenceRecord(
                    record_id="record-two",
                    revision="rev-2",
                    canonical_uri="tabula://corpus/record-two/rev-2",
                    content="second bounded fact",
                    retrieved_at="2026-09-18T00:02:00Z",
                ),
            ),
        )


class BlockingEvidenceReader(EvidenceReader):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def read(self, request):
        self.started.set()
        if not self.release.wait(timeout=10):
            raise TimeoutError("test evidence read was not released")
        return super().read(request)


class GroundedCognition:
    def __init__(self, citations=None):
        self.requests = []
        self.citations = citations

    def run(self, request):
        self.requests.append(request)
        references = (
            tuple(item.reference_id for item in request.evidence)
            if self.citations is None
            else self.citations
        )
        return AgentCognitionResult(
            request_id=request.request_id,
            agent_id=request.agent_id,
            work_item_id=request.work_item_id,
            attempt_id=request.attempt_id,
            mission_id=request.mission_id,
            mission_version=request.mission_version,
            summary="Evidence supports the bounded conclusion.",
            evidence_references=references,
        )


class GroundedScoutTests(unittest.TestCase):
    def setUp(self):
        reset_runtime_database()
        self.authority = Authority()
        self.context = MissionContext()
        self.reader = EvidenceReader()
        self.cognition = GroundedCognition()
        self.owner = Principal(
            PrincipalType.HUMAN,
            "owner",
            frozenset({"MISSION_OWNER", "OPERATOR"}),
        )
        self.runtime = self._runtime()
        self.centurion, self.centurion_assignment, self.centurion_binding = (
            self._create_assigned("centurion")
        )
        self.scout, self.scout_assignment, self.scout_binding = (
            self._create_assigned("scout")
        )

    def tearDown(self):
        self.runtime.close()

    def _runtime(self, *, reader=None, cognition=None):
        return PersistentAgentRuntime(
            new_runtime_store(),
            self.authority,
            mission_context=self.context,
            cognition=cognition or self.cognition,
            evidence_reader=reader or self.reader,
        )

    def _create_assigned(self, role):
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
            workload=Principal(PrincipalType.WORKLOAD, f"{role}-workload"),
            delegation_id=f"{role}-grant",
            correlation_id=CORRELATION,
            idempotency_key=f"resume-{role}",
        )
        return agent, assignment, resumed.binding

    def _delegate(self, *, objective="What evidence supports the objective?"):
        return self.runtime.delegate_work(
            centurion_binding_id=self.centurion_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "centurion-workload"),
            scout_assignment_id=self.scout_assignment.assignment_id,
            objective=objective,
            required_capabilities=("read_only_analysis", "tabula_corpus_read"),
            correlation_id=CORRELATION,
            idempotency_key="delegate-grounded",
            work_kind=WorkKind.GROUNDED_CORPUS_ANALYSIS,
        )

    def _claim(self, work):
        return self.runtime.claim_work(
            work_item_id=work.work_item_id,
            scout_binding_id=self.scout_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload"),
            idempotency_key="claim-grounded",
        )

    def _execute(self, runtime=None):
        runtime = runtime or self.runtime
        work = runtime.list_work_for_assignment(self.scout_assignment.assignment_id)[0]
        return runtime.execute_scout_work(
            work_item_id=work.work_item_id,
            scout_binding_id=self.scout_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload"),
            idempotency_key="execute-grounded",
        )

    def test_grounded_result_persists_safe_provenance_and_survives_restart(self):
        work = self._delegate()
        self._claim(work)
        result = self._execute()

        self.assertEqual(work.kind, WorkKind.GROUNDED_CORPUS_ANALYSIS)
        self.assertEqual(len(result.evidence_references), 2)
        self.assertEqual(len(self.context.calls), 1)
        self.assertEqual(len(self.reader.calls), 1)
        request = self.cognition.requests[0]
        self.assertEqual(request.logical_capability, "grounded_corpus_analysis")
        self.assertEqual(len(request.evidence), 2)
        references = self.runtime.list_work_evidence_references(
            work_item_id=work.work_item_id
        )
        self.assertEqual(
            set(result.evidence_references),
            {item.evidence_reference_id for item in references},
        )
        self.assertTrue(all(item.scope_binding_version == "1.0.0" for item in references))
        snapshot = RepositoryMissionOrganizationReadModel(
            self.runtime.repository
        ).snapshot(
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_id=MISSION,
        )
        self.assertEqual(len(snapshot.agents), 2)
        self.assertEqual(snapshot.work[0].result_summary, result.summary)
        self.assertEqual(
            {item.external_record_id for item in snapshot.work[0].evidence},
            {"record-one", "record-two"},
        )
        self.assertNotIn("sensitive evidence sentinel", repr(snapshot))
        events = self.runtime.list_events(self.scout.agent_id)
        durable_text = repr(references) + repr(events) + repr(result)
        self.assertNotIn("sensitive evidence sentinel", durable_text)

        self.runtime.close()
        self.runtime = self._runtime()
        restarted = self.runtime.get_work_result(work.work_item_id)
        self.assertEqual(restarted.result_id, result.result_id)
        self.assertEqual(
            len(
                self.runtime.list_work_evidence_references(
                    work_item_id=work.work_item_id
                )
            ),
            2,
        )

    def test_grounded_objective_limit_fails_before_persistence_or_authority(self):
        with self.assertRaisesRegex(RuntimeOperationError, "GROUNDED_OBJECTIVE_TOO_LONG"):
            self._delegate(objective="x" * 2001)
        self.assertEqual(
            self.runtime.list_work_for_assignment(self.scout_assignment.assignment_id),
            [],
        )
        self.assertEqual(self.context.calls, [])
        self.assertEqual(self.reader.calls, [])

    def test_knowledge_denial_prevents_cognition_and_result(self):
        work = self._delegate()
        self._claim(work)
        self.reader.error = AuthorityDenied("DELEGATION_REVOKED")
        with self.assertRaisesRegex(RuntimeOperationError, "DELEGATION_REVOKED"):
            self._execute()
        self.assertEqual(self.cognition.requests, [])
        self.assertIsNone(self.runtime.get_work_result(work.work_item_id))
        self.assertEqual(self.runtime.get_work_item(work.work_item_id).status, WorkStatus.FAILED)
        events = self.runtime.list_events(self.scout.agent_id)
        self.assertTrue(any(event.event_type == "GroundedEvidenceFailed" for event in events))

    def test_unknown_or_duplicate_citation_rejects_result(self):
        work = self._delegate()
        self._claim(work)
        invalid = GroundedCognition(citations=("77777777-7777-4777-8777-777777777777",))
        self.runtime.cognition = invalid
        with self.assertRaisesRegex(
            RuntimeOperationError, "COGNITION_EVIDENCE_REFERENCES_INVALID"
        ):
            self._execute()
        self.assertIsNone(self.runtime.get_work_result(work.work_item_id))
        self.assertEqual(self.runtime.get_work_item(work.work_item_id).status, WorkStatus.FAILED)

    def test_reconcile_uses_persisted_external_stage(self):
        work = self._delegate()
        attempt = self._claim(work)
        with self.runtime.repository.transaction(
            lock_keys=self.runtime._work_lock_keys(work)
        ):
            self.runtime.repository.save_work_attempt(
                replace(
                    attempt,
                    status=AttemptStatus.RUNNING,
                    attempt_stage=AttemptStage.EVIDENCE_RETRIEVAL,
                    version=2,
                ),
                expected_previous_version=1,
            )
        reconciled = self.runtime.reconcile_work(
            work_item_id=work.work_item_id,
            scout_binding_id=self.scout_binding.binding_id,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload"),
            idempotency_key="reconcile-grounded",
        )
        self.assertEqual(reconciled.status, WorkStatus.RETRYABLE)
        stored = self.runtime.repository.get_work_attempt(attempt.attempt_id)
        self.assertEqual(stored.error_code, "AMBIGUOUS_EVIDENCE_RETRIEVAL")

    def test_cancellation_during_retrieval_discards_late_bundle(self):
        work = self._delegate()
        self._claim(work)
        blocking = BlockingEvidenceReader()

        def execute():
            runtime = self._runtime(reader=blocking)
            try:
                return self._execute(runtime)
            finally:
                runtime.close()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(execute)
            self.assertTrue(blocking.started.wait(timeout=10))
            self.runtime.cancel_work(
                work_item_id=work.work_item_id,
                centurion_binding_id=self.centurion_binding.binding_id,
                workload=Principal(PrincipalType.WORKLOAD, "centurion-workload"),
                reason="Investigation superseded",
                idempotency_key="cancel-grounded",
            )
            blocking.release.set()
            with self.assertRaisesRegex(RuntimeOperationError, "WORK_CANCELLED"):
                future.result(timeout=10)
        self.assertEqual(
            self.runtime.list_work_evidence_references(work_item_id=work.work_item_id),
            [],
        )
        self.assertIsNone(self.runtime.get_work_result(work.work_item_id))


if __name__ == "__main__":
    unittest.main()
