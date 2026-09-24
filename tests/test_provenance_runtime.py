from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, update

from aquila_api import PersistentAquilaService
from legion_runtime import AttemptStage, AttemptStatus, PersistentAgentRuntime, RuntimeOperationError, WorkKind
from legion_runtime.database import runtime_work_evidence_references, runtime_work_items
from legion_runtime.provenance import ProvenanceAssessment
from legion_runtime.repository import AgentStoreConflict
from legion_runtime.work import EvidenceCheckpoint
from tests import test_authorized_cognition as authorized
from tests.cognition_http import final_response
from tests.runtime_postgres import new_runtime_store, reset_runtime_database, runtime_test_database_url


class ProcessLoss(BaseException):
    pass


def delegate(state, key="provenance-work", objective="Find architecture evidence"):
    return state["runtime"].delegate_work(
        centurion_binding_id=state["centurion_binding"].binding_id,
        workload=state["centurion_workload"], scout_assignment_id=state["scout_assignment"].assignment_id,
        objective=objective,
        required_capabilities=("read_only_analysis", "model_reasoning", "tabula_corpus_read"),
        correlation_id=state["scout_binding"].correlation_id, idempotency_key=key,
        work_kind=WorkKind.PROVENANCE_BOUND_CORPUS_ANALYSIS)


class ProvenanceRuntimeTests(unittest.TestCase):
    state = authorized.AuthorizedCognitionTests.state

    def setUp(self):
        reset_runtime_database()

    def interrupted(self):
        runner, state, peer = self.state([final_response()])
        work = delegate(state)
        with patch.object(ProvenanceAssessment, "finish", side_effect=ProcessLoss):
            with self.assertRaises(ProcessLoss):
                runner._claim_and_execute(state, work)
        work = state["runtime"].repository.get_work_item(work.work_item_id)
        self.assertIsNotNone(work.evidence_checkpoint)
        return runner, state, peer, work

    def recover(self, state, work):
        runtime = state["runtime"]
        runtime.reconcile_work(work_item_id=work.work_item_id,
            scout_binding_id=state["scout_binding"].binding_id,
            workload=state["scout_workload"], idempotency_key="reconcile-provenance")

    def test_one_authorized_assessment_seals_only_content_provenance(self):
        runner, state, peer = self.state([final_response()])
        work = delegate(state)
        attempt, result = runner._claim_and_execute(state, work)
        rows = state["runtime"].repository.list_work_evidence_references(work_item_id=work.work_item_id)
        retained = state["runtime"].repository.get_work_item(work.work_item_id)
        self.assertEqual(retained.evidence_checkpoint.reference_ids, tuple(row.evidence_reference_id for row in rows))
        chats = [body for _, body, _ in peer.requests if body is not None]
        self.assertEqual(len(chats), 1)
        self.assertNotIn("tools", chats[0])
        content = "non-durable raw acceptance evidence"
        self.assertEqual(rows[0].content_sha256, sha256(content.encode()).hexdigest())
        self.assertEqual(rows[0].content_bytes, len(content.encode()))
        self.assertNotIn(content, repr(retained) + repr(rows))
        self.assertEqual(result.evidence_references, retained.evidence_checkpoint.reference_ids)
        turns = state["runtime"].repository.list_cognition_turns(work.work_item_id)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["status"], "SUCCESS")
        self.assertEqual(state["cognition"].calls, 0)

    def test_reconstructed_runtime_rereads_checkpoint_with_new_citations_and_authority(self):
        runner, state, peer, work = self.interrupted()
        original = state["runtime"].repository.list_work_evidence_references(work_item_id=work.work_item_id)
        state["runtime"].close()
        state["runtime"] = PersistentAgentRuntime(new_runtime_store(), state["mission_authority"],
            mission_context=state["mission_authority"], evidence_reader=state["evidence_reader"],
            cognition_invoker=state["invoker"])
        self.recover(state, work)
        with patch.object(state["evidence_reader"], "read", side_effect=AssertionError("SEARCH_MUST_NOT_RUN")), \
                patch.object(state["evidence_reader"], "reread", wraps=state["evidence_reader"].reread) as reread:
            attempt, result = runner._claim_and_execute(state, work, "replacement")
        self.assertEqual(reread.call_count, 1)
        self.assertEqual(attempt.attempt_number, 2)
        self.assertNotEqual(result.evidence_references, work.evidence_checkpoint.reference_ids)
        current = state["runtime"].repository.list_work_evidence_references(attempt_id=result.attempt_id)
        self.assertEqual(current[0].content_sha256, original[0].content_sha256)
        self.assertNotEqual(current[0].successful_authorization_decision_id, original[0].successful_authorization_decision_id)
        self.assertEqual(state["runtime"].repository.get_work_item(work.work_item_id).evidence_checkpoint, work.evidence_checkpoint)

    def test_changed_content_refuses_without_cognition_or_fallback(self):
        runner, state, peer, work = self.interrupted()
        self.recover(state, work)
        client = state["evidence_reader"].client
        original = client._transport
        def changed(token, request):
            response = original(token, request)
            response.body["results"][0]["content"] = "replacement evidence"
            return response
        client._transport = changed
        with patch.object(state["evidence_reader"], "read", side_effect=AssertionError("NO_SEARCH")):
            with self.assertRaisesRegex(RuntimeOperationError, "TABULA_PROTOCOL_ERROR"):
                runner._claim_and_execute(state, work, "replacement")
        self.assertFalse(any(body is not None for _, body, _ in peer.requests))
        self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))

    def test_missing_reference_and_corrupt_checkpoint_never_trigger_search(self):
        for corrupt in ("missing_row", "bad_shape", "lost_seal"):
            reset_runtime_database()
            runner, state, peer, work = self.interrupted()
            self.recover(state, work)
            engine = state["runtime"].repository.engine
            with engine.begin() as connection:
                if corrupt == "lost_seal":
                    connection.execute(update(runtime_work_items).where(runtime_work_items.c.work_item_id == work.work_item_id)
                                       .values(evidence_checkpoint=None))
                elif corrupt == "bad_shape":
                    connection.execute(update(runtime_work_items).where(runtime_work_items.c.work_item_id == work.work_item_id)
                                       .values(evidence_checkpoint={"projection": "unknown", "reference_ids": []}))
                else:
                    connection.execute(delete(runtime_work_evidence_references))
            with patch.object(state["evidence_reader"], "read", side_effect=AssertionError("NO_SEARCH")), \
                    patch.object(state["evidence_reader"], "reread", side_effect=AssertionError("NO_REREAD")):
                with self.assertRaisesRegex(RuntimeOperationError, "EVIDENCE_CHECKPOINT_INVALID"):
                    runner._claim_and_execute(state, work, "replacement")

    def test_repository_cannot_clear_or_replace_established_checkpoint(self):
        _, state, _, work = self.interrupted()
        for checkpoint in (None, EvidenceCheckpoint((str(uuid4()),))):
            with self.assertRaises(AgentStoreConflict):
                with state["runtime"].repository.transaction(lock_keys=state["runtime"]._work_lock_keys(work)):
                    state["runtime"].repository.save_work_item(
                        replace(work, evidence_checkpoint=checkpoint, version=work.version + 1),
                        expected_previous_version=work.version)
        self.assertEqual(state["runtime"].repository.get_work_item(work.work_item_id), work)

    def test_cross_instance_revocation_after_allow_stops_inference_dispatch(self):
        runner, state, peer = self.state([final_response()])
        original = state["inference_authority"].authorize
        def authorize(context, facts):
            result = original(context, facts)
            other = PersistentAquilaService(str(Path(state["directory"]) / "aquila.sqlite3"))
            try:
                other.revoke_delegation(actor=runner.owner, mission_id=state["mission_id"],
                    delegation_id=state["scout_grant"], reason="revoke after allow")
            finally:
                other.close()
            return result
        state["inference_authority"].authorize = authorize
        work = delegate(state)
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        self.assertFalse(any(body is not None for _, body, _ in peer.requests))

    def test_new_work_refuses_lossy_downgrade_and_metadata_has_no_drift(self):
        _, state, _ = self.state([final_response()])
        work = delegate(state)
        with patch.dict(os.environ, LEGION_RUNTIME_DATABASE_URL=runtime_test_database_url()):
            config = Config("legion_runtime/alembic.ini")
            command.check(config)
            with self.assertRaisesRegex(RuntimeError, "provenance-bound evidence exists"):
                command.downgrade(config, "0005")
        self.assertEqual(state["runtime"].repository.get_work_item(work.work_item_id), work)
