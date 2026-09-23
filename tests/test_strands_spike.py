"""Opt-in real isolated worker conformance; never mocks the Strands SDK."""

from dataclasses import asdict, replace
import os
import tempfile
import unittest

from experiments.strands.bridge import StrandsSpikeDriver
from legion_runtime import RuntimeOperationError, WorkKind
from legion_runtime.spike_contracts import SPIKE_CAPABILITIES
from tests.cognition_http import inference_server, tool_response, final_response, REASONING_SENTINEL
from tests.test_authorized_cognition import composition
from tests.acceptance.grounded_scout_runner import CORRELATION
from tests.runtime_postgres import reset_runtime_database


@unittest.skipUnless(os.environ.get("LEGION_STRANDS_ACCEPTANCE") == "1", "opt-in Docker/Runtime spike tests")
class StrandsRuntimeTests(unittest.TestCase):
    def setUp(self):
        reset_runtime_database()

    def state(self, responses=None):
        from contextlib import ExitStack
        stack = ExitStack()
        self.addCleanup(stack.close)
        peer = stack.enter_context(inference_server(responses))
        directory = stack.enter_context(tempfile.TemporaryDirectory(prefix="legion-strands-authority-"))
        runner, state = composition(directory, peer.origin)
        stack.callback(runner._close, state)
        state["runtime"].experimental_driver = StrandsSpikeDriver()
        return runner, state, peer

    def delegate(self, state, objective="Find architecture evidence"):
        return state["runtime"].delegate_work(
            centurion_binding_id=state["centurion_binding"].binding_id,
            workload=state["centurion_workload"], scout_assignment_id=state["scout_assignment"].assignment_id,
            objective=objective, required_capabilities=SPIKE_CAPABILITIES,
            correlation_id=CORRELATION, idempotency_key="delegate-spike", work_kind=WorkKind.COGNITION_INTEGRATION_SPIKE)

    def test_real_worker_current_workload_two_model_turns_and_safe_ledger(self):
        runner, state, peer = self.state()
        work = self.delegate(state)
        _, result = runner._claim_and_execute(state, work)
        repository = state["runtime"].repository
        trial = repository.get_spike_trial(work.work_item_id)
        facts = repository.list_spike_operations(work.work_item_id)
        self.assertEqual(trial.model_calls, 2)
        self.assertEqual(trial.retrievals, 1)
        self.assertEqual(trial.output_reserved, 4096)
        self.assertEqual(trial.active_attempt_id, result.attempt_id)
        self.assertEqual(len(result.evidence_references), 1)
        self.assertEqual([fact.status for fact in facts], ["SUCCESS"] * 3)
        model_facts = [fact.facts for fact in facts if fact.kind == "MODEL"]
        self.assertEqual(len({fact["decision_id"] for fact in model_facts}), 2)
        self.assertEqual(repository.list_cognition_turns(work.work_item_id), [])
        self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 2)
        safe = repr(facts) + repr(trial) + repr(state["aquila"].store.get_audit(state["mission_id"]))
        for sentinel in (REASONING_SENTINEL, "non-durable raw acceptance evidence", "Bearer "):
            self.assertNotIn(sentinel, safe)

    def test_more_than_two_turns_use_only_experimental_facts(self):
        second = tool_response()
        second["choices"][0]["message"]["tool_calls"][0]["id"] = "call-two"
        runner, state, peer = self.state([tool_response(), second, final_response()])
        work = self.delegate(state)
        runner._claim_and_execute(state, work)
        operations = state["runtime"].repository.list_spike_operations(work.work_item_id)
        self.assertEqual(sorted(fact.facts["turn_ordinal"] for fact in operations if fact.kind == "MODEL"), [1, 2, 3])
        self.assertEqual(state["runtime"].repository.list_cognition_turns(work.work_item_id), [])

    def test_framework_cannot_retry_after_transport_failure_and_revocation(self):
        runner, state, peer = self.state([(503, b"SYNTHETIC_FAILURE"), tool_response(), final_response()])
        driver = state["runtime"].experimental_driver
        original = state["inference_transport"].chat

        def revoke_after_failure(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            finally:
                driver.control(state["aquila"].revoke_delegation, actor=runner.owner,
                    mission_id=state["mission_id"], delegation_id=state["scout_grant"], reason="spike revocation")

        state["inference_transport"].chat = revoke_after_failure
        work = self.delegate(state)
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 1)
        self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))

    def test_runtime_cancellation_after_model_prevents_next_boundary(self):
        runner, state, peer = self.state()
        driver = state["runtime"].experimental_driver
        work = self.delegate(state)
        original = state["inference_transport"].chat

        def cancel_after_call(*args, **kwargs):
            result = original(*args, **kwargs)
            driver.control(state["runtime"].cancel_work, work_item_id=work.work_item_id,
                centurion_binding_id=state["centurion_binding"].binding_id, workload=state["centurion_workload"],
                reason="cancel in-flight spike", idempotency_key="cancel-spike")
            return result

        state["inference_transport"].chat = cancel_after_call
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 1)
        self.assertEqual(state["transport"].protected_calls, 0)
        self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))

    def test_default_runtime_rejects_experimental_work(self):
        _, state, _ = self.state()
        state["runtime"].experimental_driver = None
        with self.assertRaisesRegex(RuntimeOperationError, "EXPERIMENTAL_COGNITION_DISABLED"):
            self.delegate(state)

    def test_offering_disabled_during_authorization_prevents_first_chat(self):
        from tests.test_cognition_capability import catalog
        runner, state, peer = self.state()
        driver = state["runtime"].experimental_driver
        original = state["inference_authority"].authorize

        def disable_after_authorization(*args, **kwargs):
            result = original(*args, **kwargs)
            resources, offerings = catalog(peer.origin, revision="catalog-disabled")
            offerings = replace(offerings, offerings=(replace(offerings.offerings[0], enabled=False),))
            driver.control(state["router"].update_catalog, resources, offerings)
            return result

        state["inference_authority"].authorize = disable_after_authorization
        work = self.delegate(state)
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 0)
        self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))

    def test_grant_revoked_during_authorization_prevents_first_chat(self):
        runner, state, peer = self.state()
        driver = state["runtime"].experimental_driver
        original = state["inference_authority"].authorize

        def revoke_after_decision(*args, **kwargs):
            result = original(*args, **kwargs)
            driver.control(state["aquila"].revoke_delegation, actor=runner.owner,
                mission_id=state["mission_id"], delegation_id=state["scout_grant"],
                reason="Revoke before final model admission")
            return result

        state["inference_authority"].authorize = revoke_after_decision
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, self.delegate(state))
        self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 0)

    def test_mission_cancel_after_worker_exit_prevents_acceptance(self):
        runner, state, _ = self.state()
        driver = state["runtime"].experimental_driver
        original = driver.worker.run

        def cancel_before_commit(session, handler):
            original(session, handler)
            mission = state["aquila"].kernel.get_mission(state["mission_id"])
            response = driver.control(state["aquila"].submit_command, actor=runner.owner,
                mission_id=mission.id, body={"command_type": "CANCEL", "expected_version": mission.version,
                                            "idempotency_key": "cancel-after-worker", "payload": {}})
            self.assertEqual(response.status_code, 200)

        driver.worker.run = cancel_before_commit
        work = self.delegate(state)
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))
