from contextlib import contextmanager
from dataclasses import replace
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config

from legion_runtime import AttemptStage, AttemptStatus, PersistentAgentRuntime, RuntimeOperationError
from legion_runtime.evidence import GroundedEvidenceRereadRequest
from legion_runtime.work import EvidenceCheckpointInvalid
from tests import test_provenance_runtime as fixtures
from tests.cognition_http import final_response
from tests.runtime_postgres import new_runtime_store, runtime_test_database_url, reset_runtime_database


class ProvenanceRecoveryTests(unittest.TestCase):
    state = fixtures.ProvenanceRuntimeTests.state
    setUp = fixtures.ProvenanceRuntimeTests.setUp
    interrupted = fixtures.ProvenanceRuntimeTests.interrupted
    recover = fixtures.ProvenanceRuntimeTests.recover

    def reconstruct(self, state):
        runtime = PersistentAgentRuntime(new_runtime_store(), state["mission_authority"],
            mission_context=state["mission_authority"], evidence_reader=state["evidence_reader"],
            cognition_invoker=state["invoker"])
        self.addCleanup(runtime.close)
        return runtime

    def test_uncommitted_checkpoint_rolls_back_all_references_then_searches_again(self):
        runner, state, peer = self.state([final_response()])
        work = fixtures.delegate(state)
        runtime = state["runtime"]
        original = runtime.repository.save_work_item
        def save(item, **kwargs):
            if item.evidence_checkpoint:
                raise fixtures.ProcessLoss()
            return original(item, **kwargs)
        with patch.object(runtime.repository, "save_work_item", save):
            with self.assertRaises(fixtures.ProcessLoss):
                runner._claim_and_execute(state, work)
        self.assertIsNone(runtime.get_work_item(work.work_item_id).evidence_checkpoint)
        self.assertEqual(runtime.repository.list_work_evidence_references(work_item_id=work.work_item_id), [])
        self.recover(state, work)
        with patch.object(state["evidence_reader"], "read", wraps=state["evidence_reader"].read) as search:
            runner._claim_and_execute(state, work, "replacement")
        self.assertEqual(search.call_count, 1)

    def test_repeated_losses_at_reread_and_cognition_keep_original_checkpoint(self):
        for stage in (AttemptStage.EVIDENCE_REREAD, AttemptStage.COGNITION, AttemptStage.COGNITION_INITIAL):
            with self.subTest(stage=stage):
                reset_runtime_database()
                runner, state, peer, work = self.interrupted()
                self.recover(state, work)
                runtime = state["runtime"]
                original = runtime.repository.transaction
                crashed = False
                @contextmanager
                def transaction(**kwargs):
                    nonlocal crashed
                    with original(**kwargs):
                        yield
                    if not crashed and runtime.repository._connection is None:
                        attempt = runtime.repository.get_latest_work_attempt(work.work_item_id)
                        if attempt.attempt_number == 2 and attempt.attempt_stage == stage:
                            crashed = True
                            raise fixtures.ProcessLoss()
                with patch.object(runtime.repository, "transaction", transaction):
                    with self.assertRaises(fixtures.ProcessLoss):
                        runner._claim_and_execute(state, work, "second")
                old = runtime.repository.get_latest_work_attempt(work.work_item_id)
                replacement = self.reconstruct(state)
                replacement.reconcile_work(work_item_id=work.work_item_id,
                    scout_binding_id=state["scout_binding"].binding_id,
                    workload=state["scout_workload"], idempotency_key="recover-second")
                state["runtime"] = replacement
                self.addCleanup(runtime.close)
                with patch.object(state["evidence_reader"], "read", side_effect=AssertionError("NO_SEARCH")):
                    attempt, result = runner._claim_and_execute(state, work, "third")
                self.assertEqual(attempt.attempt_number, 3)
                self.assertEqual(replacement.get_work_item(work.work_item_id).evidence_checkpoint, work.evidence_checkpoint)
                self.assertEqual(replacement.repository.get_work_attempt(old.attempt_id).status, AttemptStatus.ABANDONED)
                self.assertEqual(len([body for _, body, _ in peer.requests if body is not None]), 1)

    def test_late_reread_cannot_publish_after_other_runtime_reconciles_and_claims(self):
        runner, state, peer, work = self.interrupted()
        self.recover(state, work)
        other = self.reconstruct(state)
        original = state["evidence_reader"].reread
        kwargs = dict(work_item_id=work.work_item_id, scout_binding_id=state["scout_binding"].binding_id,
                      workload=state["scout_workload"])
        def supersede(request):
            bundle = original(request)
            other.reconcile_work(**kwargs, idempotency_key="supersede")
            other.claim_work(**kwargs, idempotency_key="claim-third")
            return bundle
        with patch.object(state["evidence_reader"], "reread", supersede):
            with self.assertRaisesRegex(RuntimeOperationError, "WORK_RECONCILIATION_REQUIRED"):
                runner._claim_and_execute(state, work, "second")
        self.assertFalse(any(body is not None for _, body, _ in peer.requests))
        rows = other.repository.list_work_evidence_references(work_item_id=work.work_item_id)
        self.assertEqual(tuple(ref.evidence_reference_id for ref in rows), work.evidence_checkpoint.reference_ids)
        result = other.execute_scout_work(**kwargs, idempotency_key="execute-third")
        self.assertEqual(other.repository.get_latest_work_attempt(work.work_item_id).attempt_number, 3)
        self.assertEqual(other.get_work_result(work.work_item_id), result)

    def test_cancellation_after_reread_or_chat_prevents_acceptance(self):
        for boundary in ("reread", "chat"):
            with self.subTest(boundary=boundary):
                reset_runtime_database()
                runner, state, peer, work = self.interrupted()
                self.recover(state, work)
                other = self.reconstruct(state)
                target = state["evidence_reader"] if boundary == "reread" else state["inference_transport"]
                original = getattr(target, boundary)
                def cancel(*args, **kwargs):
                    response = original(*args, **kwargs)
                    other.cancel_work(work_item_id=work.work_item_id,
                        centurion_binding_id=state["centurion_binding"].binding_id,
                        workload=state["centurion_workload"], reason="cancel recovery",
                        idempotency_key="cancel-recovery")
                    return response
                with patch.object(target, boundary, cancel):
                    with self.assertRaisesRegex(RuntimeOperationError, "WORK_CANCELLED"):
                        runner._claim_and_execute(state, work, "replacement")
                self.assertIsNone(other.get_work_result(work.work_item_id))
                self.assertEqual(len([body for _, body, _ in peer.requests if body is not None]), int(boundary == "chat"))

    def test_cross_work_and_mixed_origin_references_are_rejected_before_authority(self):
        _, state, _, work = self.interrupted()
        reference = state["runtime"].repository.list_work_evidence_references(work_item_id=work.work_item_id)[0]
        common = dict(organization_id=state["scout"].organization_id, workspace_id=state["scout"].workspace_id,
            mission_id=work.mission_id, agent_id=work.scout_agent_id, assignment_id=work.scout_assignment_id,
            workload=state["scout_workload"], delegation_id=state["scout_grant"], work_item_id=work.work_item_id,
            attempt_id=str(uuid4()), correlation_id=work.correlation_id)
        for changes in ({"work_item_id": str(uuid4())}, {"scope_binding_id": "not-a-binding"},
                        {"content_sha256": None, "content_bytes": None}):
            with self.assertRaises(EvidenceCheckpointInvalid):
                GroundedEvidenceRereadRequest(**common, references=(replace(reference, **changes),))
        with self.assertRaises(EvidenceCheckpointInvalid):
            GroundedEvidenceRereadRequest(**common, references=(reference, replace(reference,
                evidence_reference_id=str(uuid4()), external_record_id="second-record", attempt_id=str(uuid4()))))

    def test_populated_legacy_migration_roundtrip_preserves_nullable_provenance(self):
        runner, state, _ = self.state([final_response()])
        work = runner._delegate(state)
        _, result = runner._claim_and_execute(state, work)
        store = state["runtime"].repository
        original = store.list_work_evidence_references(work_item_id=work.work_item_id)
        with patch.dict(os.environ, LEGION_RUNTIME_DATABASE_URL=runtime_test_database_url()):
            config = Config("legion_runtime/alembic.ini")
            command.downgrade(config, "0005")
            command.upgrade(config, "head")
            command.check(config)
        self.assertEqual(store.list_work_evidence_references(work_item_id=work.work_item_id), original)
        self.assertTrue(all(ref.content_bytes is None and ref.content_sha256 is None for ref in original))
        self.assertIsNone(store.get_work_item(work.work_item_id).evidence_checkpoint)
        self.assertEqual(store.get_work_result(work.work_item_id), result)

    def test_recovery_refuses_reassignment_and_revocation_between_read_and_cognition(self):
        for control in ("binding", "grant"):
            with self.subTest(control=control):
                reset_runtime_database()
                runner, state, peer, work = self.interrupted()
                self.recover(state, work)
                original = state["evidence_reader"].reread
                def change_control(request):
                    bundle = original(request)
                    if control == "binding":
                        state["runtime"].resume_assignment(assignment_id=state["scout_assignment"].assignment_id,
                            workload=state["scout_workload"], delegation_id=state["scout_grant"],
                            correlation_id=work.correlation_id, idempotency_key="replace-recovery-binding")
                    else:
                        state["aquila"].revoke_delegation(actor=runner.owner, mission_id=work.mission_id,
                            delegation_id=state["scout_grant"], reason="revoke after reread")
                    return bundle
                with patch.object(state["evidence_reader"], "reread", change_control):
                    with self.assertRaises(RuntimeOperationError):
                        runner._claim_and_execute(state, work, "replacement")
                self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))
                self.assertFalse(any(body is not None for _, body, _ in peer.requests))

    def test_missing_invoker_or_expired_offering_cannot_use_generic_cognition(self):
        from datetime import datetime, timezone
        for condition in ("missing", "expired"):
            with self.subTest(condition=condition):
                reset_runtime_database()
                runner, state, peer = self.state([final_response()])
                work = fixtures.delegate(state)
                if condition == "missing":
                    state["runtime"].cognition_invoker = None
                else:
                    state["router"].clock = lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)
                with self.assertRaises(RuntimeOperationError):
                    runner._claim_and_execute(state, work)
                self.assertEqual(state["cognition"].calls, 0)
                self.assertFalse(any(body is not None for _, body, _ in peer.requests))

    def test_ambiguous_inference_recovers_freshly_without_conversation_replay(self):
        runner, state, peer = self.state([final_response(), final_response()])
        work = fixtures.delegate(state)
        with patch.object(state["aquila"], "record_cognition_outcome", side_effect=OSError("PRIVATE_AUDIT_FAILURE")):
            with self.assertRaises(RuntimeOperationError):
                runner._claim_and_execute(state, work)
        store = state["runtime"].repository
        checkpoint = store.get_work_item(work.work_item_id).evidence_checkpoint
        old = store.list_cognition_turns(work.work_item_id)
        self.assertEqual(old[0]["status"], "PREPARED")
        self.recover(state, work)
        with patch.object(state["evidence_reader"], "read", side_effect=AssertionError("NO_SEARCH")):
            _, result = runner._claim_and_execute(state, work, "replacement")
        chats = [body for _, body, _ in peer.requests if body is not None]
        self.assertEqual([len(body["messages"]) for body in chats], [2, 2])
        turns = store.list_cognition_turns(work.work_item_id)
        self.assertEqual([turn["turn_ordinal"] for turn in turns], [1, 1])
        self.assertNotEqual(turns[0]["decision_id"], turns[1]["decision_id"])
        self.assertEqual(store.get_work_item(work.work_item_id).evidence_checkpoint, checkpoint)
        self.assertEqual(store.get_work_result(work.work_item_id), result)
        self.assertNotIn("PRIVATE_AUDIT_FAILURE", repr(turns) + repr(state["runtime"].list_events(work.scout_agent_id)))
