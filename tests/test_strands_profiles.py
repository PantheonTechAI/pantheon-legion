"""Pinned SDK persistence/orchestration through actual isolated workers."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace

from experiments.strands.bridge import StrandsSpikeDriver
from experiments.strands.state import OperationalStore
from legion_runtime import RuntimeOperationError
from tests.cognition_http import tool_response, final_response
from tests.runtime_postgres import reset_runtime_database
from tests import test_strands_spike


def handoff():
    value = tool_response('{"agent_name":"analyst","message":"SYNTHETIC_HANDOFF"}', "handoff_to_agent")
    value["choices"][0]["message"]["tool_calls"][0]["id"] = "handoff-one"
    return value


@unittest.skipUnless(os.environ.get("LEGION_STRANDS_ACCEPTANCE") == "1", "opt-in isolated profile experiments")
class StrandsProfileTests(unittest.TestCase):
    state = test_strands_spike.StrandsRuntimeTests.state
    delegate = test_strands_spike.StrandsRuntimeTests.delegate

    def setUp(self):
        reset_runtime_database()

    def profile(self, *, mode="single", persistence="P0", responses=None, synthetic=True):
        runner, state, peer = self.state(responses)
        root = tempfile.TemporaryDirectory(prefix="legion-cognition-operational-")
        self.addCleanup(root.cleanup)
        store = OperationalStore(root.name, synthetic=synthetic) if persistence != "P0" else None
        driver = StrandsSpikeDriver(mode=mode, persistence=persistence, state_store=store)
        state["runtime"].experimental_driver = driver
        return runner, state, peer, driver, Path(root.name)

    def test_graph_and_swarm_are_internal_computation_with_fresh_physical_admissions(self):
        for mode, responses, calls in (
            ("graph", [tool_response(), final_response("research"), final_response("analysis"), final_response()], 4),
            ("swarm", [tool_response(), handoff(), final_response("coordinator"), final_response()], 4),
        ):
            with self.subTest(mode=mode):
                reset_runtime_database()
                runner, state, _, driver, _ = self.profile(mode=mode, responses=responses)
                work = self.delegate(state)
                _, result = runner._claim_and_execute(state, work)
                records = state["runtime"].repository.list_spike_operations(work.work_item_id)
                model = [item.facts for item in records if item.kind == "MODEL"]
                self.assertEqual(len(model), calls)
                self.assertEqual(len({item["decision_id"] for item in model}), calls)
                self.assertEqual(len({item.attempt_id for item in records}), 1)
                self.assertEqual(result.scout_agent_id, state["scout"].agent_id)

    def test_sanitized_and_native_state_survive_hard_worker_kill_with_fresh_evidence(self):
        for persistence in ("P1", "P2"):
            with self.subTest(persistence=persistence):
                reset_runtime_database()
                runner, state, peer, driver, root = self.profile(persistence=persistence)
                work = self.delegate(state)
                original = state["inference_transport"].chat

                def kill_before_final_response(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if result.finish_reason == "stop":
                        execution_id = driver.session.execution_id
                        driver.worker.stop_owned("legion-strands-" + execution_id, execution_id)
                    return result

                state["inference_transport"].chat = kill_before_final_response
                with self.assertRaises(RuntimeOperationError):
                    runner._claim_and_execute(state, work)
                previous = state["runtime"].repository.get_spike_trial(work.work_item_id)
                snapshot = root / work.work_item_id / "1.json"
                self.assertTrue(snapshot.is_file())
                text = snapshot.read_text()
                self.assertNotIn("EXPLICIT_REASONING_SENTINEL_DO_NOT_RETAIN", text)
                if persistence == "P1":
                    self.assertNotIn("non-durable raw acceptance evidence", text)
                    self.assertNotIn("Find architecture evidence", text)
                else:
                    self.assertIn("non-durable raw acceptance evidence", text)
                state["inference_transport"].chat = original
                driver.control(state["runtime"].reconcile_work, work_item_id=work.work_item_id,
                    scout_binding_id=state["scout_binding"].binding_id, workload=state["scout_workload"],
                    idempotency_key="profile-reconcile")
                peer.responses.extend([tool_response(), final_response()])
                runner._claim_and_execute(state, work, "restored")
                self.assertTrue(driver.restored)
                current = state["runtime"].repository.get_spike_trial(work.work_item_id)
                self.assertEqual(current.model_calls, 4)
                self.assertEqual(current.retrievals, 3)  # initial, pre-restore fresh read, current worker read
                self.assertNotEqual(previous.active_attempt_id, current.active_attempt_id)
                chats = [body for _, body, _ in peer.requests if body is not None]
                self.assertEqual(len(chats[2]["messages"]) > len(chats[0]["messages"]), persistence == "P2")
                other = root / "unrelated-trial"
                other.mkdir()
                driver.state_store.delete(driver.session)
                self.assertFalse((root / work.work_item_id).exists())
                self.assertTrue(other.exists())

    def test_swarm_may_finish_at_coordinator_without_handoff(self):
        for persistence in ("P0", "P1", "P2"):
            with self.subTest(persistence=persistence):
                reset_runtime_database()
                runner, state, peer, _, _ = self.profile(mode="swarm", persistence=persistence,
                    responses=[tool_response(), final_response("coordinator final")])
                work = self.delegate(state)
                _, result = runner._claim_and_execute(state, work)
                self.assertEqual(result.summary, "coordinator final")
                self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 2)

    def test_swarm_uses_last_completed_node_after_return_handoff(self):
        back = tool_response('{"agent_name":"coordinator","message":"Return assessment"}', "handoff_to_agent")
        back["choices"][0]["message"]["tool_calls"][0]["id"] = "handoff-back"
        runner, state, peer, _, _ = self.profile(mode="swarm", responses=[tool_response(), handoff(),
            final_response("earlier coordinator"), back, final_response("earlier analyst"),
            final_response("latest coordinator")])
        _, result = runner._claim_and_execute(state, self.delegate(state))
        self.assertEqual(result.summary, "latest coordinator")
        self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 6)

    def test_native_state_requires_explicit_synthetic_composition(self):
        runner, state, peer, _, _ = self.profile(persistence="P2", synthetic=False)
        with self.assertRaisesRegex(RuntimeOperationError, "SPIKE_NATIVE_REQUIRES_SYNTHETIC_DATA"):
            runner._claim_and_execute(state, self.delegate(state))
        self.assertFalse(any(body is not None for _, body, _ in peer.requests))

    def test_multiple_tool_calls_rejected_before_any_tool_or_handoff(self):
        for mode in ("single", "swarm"):
            with self.subTest(mode=mode):
                reset_runtime_database()
                multiple = tool_response()
                extra = handoff() if mode == "swarm" else tool_response()
                second = extra["choices"][0]["message"]["tool_calls"][0]
                second["id"] = "second-tool"
                multiple["choices"][0]["message"]["tool_calls"].append(second)
                runner, state, peer, _, _ = self.profile(mode=mode, responses=[
                    multiple, final_response("coordinator"), final_response("analyst")])
                work = self.delegate(state)
                with self.assertRaisesRegex(RuntimeOperationError, "SPIKE_MULTIPLE_TOOL_CALLS"):
                    runner._claim_and_execute(state, work)
                self.assertEqual(state["transport"].protected_calls, 0)
                self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 1)
                self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))
                operations = state["runtime"].repository.list_spike_operations(work.work_item_id)
                self.assertEqual(len(operations), 1)
                self.assertEqual(operations[0].status, "FAILED")
                self.assertEqual(operations[0].facts["error_code"], "SPIKE_MULTIPLE_TOOL_CALLS")

    def test_native_graph_and_swarm_resume_after_hard_worker_kill(self):
        for mode, replies, kill_call in (
            ("graph", [tool_response(), final_response("research"), final_response("analysis")], 3),
            ("swarm", [tool_response(), handoff(), final_response("coordinator"), final_response("analyst")], 4),
        ):
            with self.subTest(mode=mode):
                reset_runtime_database()
                runner, state, peer, driver, root = self.profile(mode=mode, persistence="P2", responses=replies)
                work = self.delegate(state)
                original = state["inference_transport"].chat
                calls = []

                def kill_in_progress(*args, **kwargs):
                    result = original(*args, **kwargs)
                    calls.append(result)
                    if len(calls) == kill_call:
                        execution_id = driver.session.execution_id
                        driver.worker.stop_owned("legion-strands-" + execution_id, execution_id)
                    return result

                state["inference_transport"].chat = kill_in_progress
                with self.assertRaises(RuntimeOperationError):
                    runner._claim_and_execute(state, work)
                self.assertTrue((root / work.work_item_id / "1.json").is_file())
                state["inference_transport"].chat = original
                driver.control(state["runtime"].reconcile_work, work_item_id=work.work_item_id,
                    scout_binding_id=state["scout_binding"].binding_id, workload=state["scout_workload"],
                    idempotency_key="orchestrator-reconcile")
                peer.responses.extend([final_response(), final_response()])
                runner._claim_and_execute(state, work, "orchestrator-restored")
                self.assertTrue(driver.restored)
                trial = state["runtime"].repository.get_spike_trial(work.work_item_id)
                self.assertLessEqual(trial.model_calls, kill_call + 2)
                self.assertEqual(trial.retrievals, 2)
                self.assertEqual(len({span["trace_id"] for span in driver.telemetry}), 1)

    def test_content_sentinels_absent_from_native_otel_and_sanitized_store(self):
        runner, state, peer, driver, root = self.profile(persistence="P1", responses=[
            tool_response('{"query":"TOOL_ARG_SENTINEL_DO_NOT_RETAIN"}'), final_response()])
        original = state["runtime"].evidence_reader.client._transport

        def evidence(token, request):
            response = original(token, request)
            response.body["results"][0]["content"] = "EVIDENCE_SENTINEL_DO_NOT_RETAIN TOOL_RESULT_SENTINEL_DO_NOT_RETAIN"
            return response

        state["runtime"].evidence_reader.client._transport = evidence
        work = self.delegate(state, objective="PROMPT_SENTINEL_DO_NOT_RETAIN")
        runner._claim_and_execute(state, work)
        self.assertTrue(driver.telemetry)
        trial = state["runtime"].repository.get_spike_trial(work.work_item_id)
        self.assertTrue(all(span["trace_id"] == trial.trace_id for span in driver.telemetry))
        safe = json.dumps(driver.telemetry) + (root / work.work_item_id / "1.json").read_text()
        for sentinel in ("PROMPT_SENTINEL_DO_NOT_RETAIN", "TOOL_ARG_SENTINEL_DO_NOT_RETAIN",
                         "EVIDENCE_SENTINEL_DO_NOT_RETAIN", "TOOL_RESULT_SENTINEL_DO_NOT_RETAIN",
                         "EXPLICIT_REASONING_SENTINEL_DO_NOT_RETAIN", "SECRET_SENTINEL_DO_NOT_RETAIN"):
            self.assertNotIn(sentinel, safe)

    def test_changed_evidence_scope_prevents_continuation(self):
        runner, state, peer, driver, _ = self.profile()
        reader = state["runtime"].evidence_reader
        original = reader.client._transport

        def change_scope(token, request):
            response = original(token, request)
            driver.control(setattr, reader, "binding", replace(reader.binding, version="2.0.0"))
            return response

        reader.client._transport = change_scope
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, self.delegate(state))
        self.assertEqual(len([body for _, body, _ in peer.requests if body is not None]), 1)

    def test_tampered_snapshot_rejected_before_replacement_model_dispatch(self):
        runner, state, peer, driver, root = self.profile(persistence="P1")
        work = self.delegate(state)
        original = driver.worker.run

        def stop_after_snapshot(session, handler):
            original(session, handler)
            raise OSError("SYNTHETIC_BROKER_LOSS_AFTER_SNAPSHOT")

        driver.worker.run = stop_after_snapshot
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        path = root / work.work_item_id / "1.json"
        snapshot = json.loads(path.read_text())
        snapshot["scope"]["mission_id"] = "forged-mission"
        path.write_text(json.dumps(snapshot))
        driver.worker.run = original
        driver.control(state["runtime"].reconcile_work, work_item_id=work.work_item_id,
            scout_binding_id=state["scout_binding"].binding_id, workload=state["scout_workload"],
            idempotency_key="tampered-reconcile")
        before = len([body for _, body, _ in peer.requests if body is not None])
        with self.assertRaisesRegex(RuntimeOperationError, "SPIKE_SNAPSHOT_REFUSED"):
            runner._claim_and_execute(state, work, "tampered")
        self.assertEqual(len([body for _, body, _ in peer.requests if body is not None]), before)
        self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))
