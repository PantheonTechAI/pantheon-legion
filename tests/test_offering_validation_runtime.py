"""Sequential real PostgreSQL/Aquila maintenance admission and publication."""

from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from legion_cognition.offering_validation import Candidate, OfferingValidator, ValidationBundle, utcnow
from legion_runtime import RuntimeOperationError
from tests.acceptance.validate_offering import MaintenanceCognition, maintenance_composition
from tests.cognition_http import inference_server, REASONING_SENTINEL
from tests.runtime_postgres import reset_runtime_database
from tests.test_offering_validation import candidate_config, initial_response, continuation, Observer, transport


class OfferingValidationRuntimeTests(unittest.TestCase):
    def setUp(self):
        reset_runtime_database()

    def test_runtime_acceptance_and_current_aquila_decisions_precede_publication(self):
        with inference_server([initial_response(), continuation]) as peer, tempfile.TemporaryDirectory() as directory:
            bundle = ValidationBundle(Path(directory) / "bundle")
            runner, state = maintenance_composition(bundle.root)
            try:
                validator = OfferingValidator(Candidate(candidate_config(peer.origin)), Observer(), transport())
                adapter = MaintenanceCognition(state, validator)
                state["runtime"].cognition = adapter
                grant = state["aquila"].delegations[state["scout_binding"].grant_id]
                self.assertEqual(grant.allowed_operations, frozenset({"READ_MISSION", "INVOKE_COGNITION"}))
                from legion_resource.inference import timestamp
                self.assertLess(timestamp(grant.expires_at) - utcnow(), timedelta(minutes=11))
                work = runner._delegate(state, grounded=False, objective="CFV-001 synthetic offering maintenance")
                _, result = runner._claim_and_execute(state, work)
                path = bundle.publish(validator, accepted_result=result, guard=lambda: adapter.publication_guard(result))
                self.assertTrue(path.exists())
                facts = state["runtime"].repository.list_cognition_turns(work.work_item_id)
                self.assertEqual(len(facts), 2)
                self.assertEqual(len({f["decision_id"] for f in facts}), 2)
                self.assertEqual({f["status"] for f in facts}, {"SUCCESS"})
                audit = state["aquila"].store.get_audit(work.mission_id)
                self.assertEqual(sum(e.event_type == "COGNITION_AUTHORIZATION_EVALUATED" for e in audit), 2)
                self.assertNotIn(REASONING_SENTINEL, repr(facts) + repr(audit) + path.read_text()
                                 + (bundle.root / "report.json").read_text())
                self.assertEqual(state["transport"].protected_calls, 0)
            finally:
                runner._close(state)
                bundle.close()

    def test_revocation_cancellation_and_audit_failure_stop_next_physical_call(self):
        for failure in ("revoke", "cancel", "audit"):
            with self.subTest(failure=failure), inference_server([initial_response(), continuation]) as peer, tempfile.TemporaryDirectory() as directory:
                reset_runtime_database()
                runner, state = maintenance_composition(directory)
                try:
                    wire = transport()
                    validator = OfferingValidator(Candidate(candidate_config(peer.origin)), Observer(), wire)
                    state["runtime"].cognition = MaintenanceCognition(state, validator)
                    work = runner._delegate(state, grounded=False, objective="CFV-001 synthetic offering maintenance")
                    original = wire.probe
                    def fail_after_first(*args, **kwargs):
                        response = original(*args, **kwargs)
                        if failure == "revoke":
                            state["aquila"].revoke_delegation(actor=runner.owner, mission_id=work.mission_id,
                                delegation_id=state["scout_binding"].grant_id, reason="CFV test revocation")
                        elif failure == "cancel":
                            state["runtime"].cancel_work(work_item_id=work.work_item_id,
                                centurion_binding_id=state["centurion_binding"].binding_id,
                                workload=state["centurion_workload"], reason="CFV cancellation", idempotency_key="cfv-cancel")
                        else:
                            state["aquila"].record_cognition_outcome = lambda **kwargs: (_ for _ in ()).throw(OSError("SECRET_AUDIT"))
                        return response
                    wire.probe = fail_after_first
                    with self.assertRaises(RuntimeOperationError):
                        runner._claim_and_execute(state, work)
                    self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 1)
                    self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))
                    self.assertIsNone(validator.catalog)
                    self.assertNotIn("SECRET_AUDIT", repr(validator.report))
                finally:
                    runner._close(state)

    def test_revocation_after_authorization_prevents_initial_transport(self):
        from aquila_api.runtime_authority import InProcessAquilaCognitionAuthority
        from unittest.mock import patch
        with inference_server([initial_response(), continuation]) as peer, tempfile.TemporaryDirectory() as directory:
            runner, state = maintenance_composition(directory)
            try:
                validator = OfferingValidator(Candidate(candidate_config(peer.origin)), Observer(), transport())
                state["runtime"].cognition = MaintenanceCognition(state, validator)
                work = runner._delegate(state, grounded=False, objective="CFV-001 synthetic offering maintenance")
                original = InProcessAquilaCognitionAuthority.authorize
                def revoke(authority, context, facts):
                    decision = original(authority, context, facts)
                    state["aquila"].revoke_delegation(actor=runner.owner, mission_id=work.mission_id,
                        delegation_id=state["scout_binding"].grant_id, reason="CFV admission revocation")
                    return decision
                with patch.object(InProcessAquilaCognitionAuthority, "authorize", revoke), self.assertRaises(RuntimeOperationError):
                    runner._claim_and_execute(state, work)
                self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 0)
                self.assertIsNone(validator.catalog)
            finally:
                runner._close(state)
