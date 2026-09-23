"""Synthetic action boundary tests with real Aquila, Runtime and Strands workers."""

from dataclasses import replace
from datetime import datetime, timedelta
import os
from pathlib import Path
import tempfile
import unittest

from aquila_api.spike_actions import SpikeActionAuthority
from experiments.strands.bridge import StrandsSpikeDriver
from experiments.strands.enforcer import ReviewMarkerFixture
from legion_kernel import AuthorizationError, RoeLevel
from legion_runtime import RuntimeOperationError
from tests.acceptance.grounded_scout_runner import CORRELATION
from tests.cognition_http import tool_response, final_response
from tests.runtime_postgres import reset_runtime_database
from tests import test_strands_spike


def action_response():
    value = tool_response('{"marker":"reviewed"}', "fixture_record_review")
    value["choices"][0]["message"]["tool_calls"][0]["id"] = "call-action"
    return value


@unittest.skipUnless(os.environ.get("LEGION_STRANDS_ACCEPTANCE") == "1", "opt-in isolated spike action tests")
class StrandsActionTests(unittest.TestCase):
    state = test_strands_spike.StrandsRuntimeTests.state
    delegate = test_strands_spike.StrandsRuntimeTests.delegate

    def setUp(self):
        reset_runtime_database()

    def setup_action(self, *, review=True):
        runner, state, peer = self.state([tool_response(), action_response()])
        aquila, runtime = state["aquila"], state["runtime"]
        driver = StrandsSpikeDriver(action_authority=SpikeActionAuthority(aquila))
        runtime.experimental_driver = driver
        directory = tempfile.TemporaryDirectory(prefix="legion-strands-effect-")
        self.addCleanup(directory.cleanup)
        driver.enforcer = ReviewMarkerFixture(database=str(Path(directory.name) / "effects.sqlite3"),
            authority=driver.action_authority, gate=driver.gate, current_scope=driver.action_scope)
        self.addCleanup(driver.enforcer.close)
        if review:
            # The authenticated fixture principal, not an adapter impersonation,
            # carries the kernel's established action-worker role.
            state["scout_workload"] = replace(state["scout_workload"], roles=frozenset({"MISSION_WORKER"}))
            mission = aquila.kernel.get_mission(state["mission_id"])
            response = driver.control(aquila.submit_command, actor=runner.owner, mission_id=mission.id,
                body={"command_type": "START", "expected_version": mission.version,
                      "idempotency_key": "spike-start", "payload": {}})
            self.assertEqual(response.status_code, 200)
            mission = aquila.kernel.get_mission(state["mission_id"])
            response = driver.control(aquila.submit_command, actor=runner.owner, mission_id=mission.id,
                body={"command_type": "SET_ROE", "expected_version": mission.version,
                      "idempotency_key": "spike-review-roe", "payload": {"level": "REVIEW",
                      "reason": "Exercise only the synthetic fixture approval boundary"}})
            self.assertEqual(response.status_code, 200)
            for role in ("centurion", "scout"):
                grant = driver.control(aquila.issue_delegation, issuer=runner.owner,
                    subject=state[role + "_workload"], mission_id=mission.id,
                    allowed_operations=frozenset({"READ_MISSION", "READ_KNOWLEDGE", "INVOKE_COGNITION", "EXECUTE_ACTION"}),
                    roe_ceiling=RoeLevel.REVIEW, expires_at="9999-01-01T00:00:00Z")
                binding = driver.control(runtime.resume_assignment,
                    assignment_id=state[role + "_assignment"].assignment_id, workload=state[role + "_workload"],
                    delegation_id=grant, correlation_id=CORRELATION, idempotency_key="resume-spike-" + role).binding
                state[role + "_binding"], state[role + "_grant"] = binding, grant
        return runner, state, peer, driver

    def approve(self, runner, state, driver):
        approvals = state["aquila"]._list_persisted_approvals(state["mission_id"])
        self.assertEqual(len(approvals), 1)
        approval = approvals[0]
        self.assertEqual(approval.status, "PENDING")
        response = driver.control(state["aquila"].decide_approval, actor=runner.owner, mission_id=state["mission_id"],
            body={"approval_id": approval.id, "expected_mission_version": approval.mission_version,
                  "decision": "APPROVE", "reason": "Approve only the synthetic reviewed marker"})
        self.assertEqual(response.status_code, 200)
        return approval

    def replacement(self, state, driver, work, suffix):
        driver.control(state["runtime"].reconcile_work, work_item_id=work.work_item_id,
            scout_binding_id=state["scout_binding"].binding_id, workload=state["scout_workload"],
            idempotency_key="reconcile-" + suffix)

    def count(self, driver):
        return driver.enforcer.connection.execute("SELECT count(*) FROM review_markers").fetchone()[0]

    def test_pending_approval_survives_worker_exit_and_fresh_attempt_executes_once(self):
        runner, state, peer, driver = self.setup_action()
        work = self.delegate(state)
        with self.assertRaisesRegex(RuntimeOperationError, "SPIKE_APPROVAL_PENDING"):
            runner._claim_and_execute(state, work)
        old = state["runtime"].repository.get_spike_trial(work.work_item_id)
        self.assertEqual(self.count(driver), 0)
        self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))
        self.approve(runner, state, driver)
        self.replacement(state, driver, work, "approved")
        peer.responses.extend([tool_response(), action_response(), final_response()])
        _, result = runner._claim_and_execute(state, work, "approved")
        trial = state["runtime"].repository.get_spike_trial(work.work_item_id)
        self.assertEqual(trial.logical_operation_id, old.logical_operation_id)
        self.assertNotEqual(trial.active_attempt_id, old.active_attempt_id)
        self.assertNotEqual(trial.execution_id, old.execution_id)
        self.assertEqual(result.scout_agent_id, state["scout"].agent_id)
        self.assertEqual(trial.model_calls, 5)
        self.assertEqual(self.count(driver), 1)
        self.assertEqual(state["aquila"]._list_persisted_approvals(state["mission_id"])[0].status, "CONSUMED")

    def test_worker_killed_after_effect_before_recording_reconciles_receipt_without_duplicate(self):
        runner, state, peer, driver = self.setup_action()
        work = self.delegate(state)
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        self.approve(runner, state, driver)
        self.replacement(state, driver, work, "approved")
        peer.responses.extend([tool_response(), action_response()])

        def kill_after_effect():
            execution_id = driver.session.execution_id
            driver.worker.stop_owned("legion-strands-" + execution_id, execution_id)
            raise OSError("SYNTHETIC_POST_EFFECT_CRASH")

        driver.enforcer.after_commit = kill_after_effect
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work, "approved")
        self.assertEqual(self.count(driver), 1)
        receipt = driver.enforcer.connection.execute("SELECT receipt_id FROM review_markers").fetchone()[0]
        self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))
        self.assertEqual(state["aquila"].store.connection.execute("SELECT count(*) FROM spike_action_receipts").fetchone()[0], 0)
        driver.enforcer.after_commit = lambda: None
        self.replacement(state, driver, work, "effect-recovery")
        peer.responses.extend([tool_response(), action_response(), final_response()])
        runner._claim_and_execute(state, work, "effect-recovery")
        self.assertEqual(self.count(driver), 1)
        self.assertEqual(driver.session.action_receipt, receipt)
        self.assertEqual(state["runtime"].repository.get_spike_trial(work.work_item_id).model_calls, 7)

    def test_denied_action_has_no_effect(self):
        runner, state, _, driver = self.setup_action(review=False)
        work = self.delegate(state)
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        self.assertEqual(self.count(driver), 0)
        self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))

    def test_enforcer_rejects_tampering_forgery_wrong_scope_expiry_and_replay(self):
        runner, state, peer, driver = self.setup_action()
        work = self.delegate(state)
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        self.approve(runner, state, driver)
        self.replacement(state, driver, work, "approved")
        peer.responses.extend([tool_response(), action_response(), final_response()])
        original = driver.enforcer.dispatch

        def attack_then_execute(permit_id, arguments):
            with self.assertRaises(AuthorizationError):
                original("forged-permit", arguments)
            with self.assertRaises(AuthorizationError):
                original(permit_id, {"marker": "changed"})
            scope = driver.action_scope()
            original_scope = driver.enforcer.current_scope
            for field in ("mission_id", "agent_id", "work_item_id", "attempt_id", "binding_id", "execution_id",
                          "assignment_id", "attempt_version", "grant_id", "logical_operation_id",
                          "correlation_id", "workload"):
                with self.subTest(forged=field):
                    value = (replace(scope.workload, subject="other-workload") if field == "workload" else
                             scope.attempt_version + 1 if field == "attempt_version" else "forged")
                    driver.enforcer.current_scope = lambda field=field, value=value: replace(scope, **{field: value})
                    with self.assertRaises(AuthorizationError):
                        original(permit_id, arguments)
                    self.assertEqual(self.count(driver), 0)
            driver.enforcer.current_scope = original_scope
            original_clock = state["aquila"].authorization.clock
            future = (datetime.fromisoformat(original_clock()) + timedelta(seconds=120)).isoformat()
            driver.control(setattr, state["aquila"].authorization, "clock", lambda: future)
            with self.assertRaises(AuthorizationError):
                original(permit_id, arguments)
            driver.control(setattr, state["aquila"].authorization, "clock", original_clock)
            receipt = original(permit_id, arguments)
            with self.assertRaises(AuthorizationError):
                original(permit_id, arguments)
            self.assertEqual(self.count(driver), 1)
            return receipt

        driver.enforcer.dispatch = attack_then_execute
        runner._claim_and_execute(state, work, "approved")
        self.assertEqual(self.count(driver), 1)
