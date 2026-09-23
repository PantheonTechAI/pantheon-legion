"""Two live containers, one broker gate; stale incarnation cannot act or commit."""

import os
import subprocess
import tempfile
import unittest

from legion_runtime import RuntimeOperationError
from tests import strands_fixture as fixture
from tests.cognition_http import inference_server, tool_response, final_response
from tests.runtime_postgres import reset_runtime_database
from tests.test_strands_actions import action_response


@unittest.skipUnless(os.environ.get("LEGION_STRANDS_ACCEPTANCE") == "1", "opt-in actual overlapping workers")
class OverlappingWorkerTests(unittest.TestCase):
    def test_replacement_fences_paused_worker_inference_action_and_result(self):
        reset_runtime_database()
        responses = [tool_response(), action_response(), tool_response(), action_response(),
                     tool_response(), action_response(), final_response()]
        with inference_server(responses) as peer, tempfile.TemporaryDirectory(prefix="legion-overlap-") as directory:
            runner, state = fixture.composition(directory, peer.origin)
            old = fixture.install_driver(state, directory, action=True)
            new = None
            try:
                fixture.enable_review(runner, state, old)
                work = fixture.delegate(state)
                with self.assertRaisesRegex(RuntimeOperationError, "SPIKE_APPROVAL_PENDING"):
                    runner._claim_and_execute(state, work)
                fixture.approve(runner, state, old)
                fixture.reconcile(state, old, work, "approved")
                transport = state["inference_transport"]
                original = transport.chat
                overlap = []

                def replace_at_action(*args, **kwargs):
                    nonlocal new
                    response = original(*args, **kwargs)
                    if not response.tool_calls or response.tool_calls[0].name != "fixture_record_review":
                        return response
                    old_name = "legion-strands-" + old.session.execution_id
                    subprocess.run(["docker", "pause", old_name], check=True, capture_output=True, timeout=10)
                    try:
                        fixture.reconcile(state, old, work, "replacement")
                        new = fixture.install_driver(state, directory, action=True, gate=old.gate)

                        def prove_overlap(*inner_args, **inner_kwargs):
                            names = [old_name, "legion-strands-" + new.session.execution_id]
                            observed = subprocess.run(["docker", "inspect", "--format",
                                "{{.State.Running}} {{.State.Paused}}", *names],
                                check=True, capture_output=True, text=True, timeout=10).stdout.splitlines()
                            self.assertEqual(observed, ["true true", "true false"])
                            with self.assertRaises(RuntimeOperationError):
                                old.action({"marker": "reviewed"})
                            with self.assertRaises(RuntimeOperationError):
                                old.model([{"role": "user", "content": "stale"}], [])
                            overlap.append(True)
                            return original(*inner_args, **inner_kwargs)

                        transport.chat = prove_overlap
                        _, accepted = runner._claim_and_execute(state, work, "replacement")
                        self.assertEqual(accepted.attempt_id, new.session.attempt.attempt_id)
                        with self.assertRaises(RuntimeOperationError):
                            old.session.guard()
                    finally:
                        transport.chat = original
                        subprocess.run(["docker", "unpause", old_name], check=True, capture_output=True, timeout=10)
                    return response

                transport.chat = replace_at_action
                with self.assertRaises(RuntimeOperationError):
                    runner._claim_and_execute(state, work, "stale")
                self.assertTrue(overlap)
                result = state["runtime"].get_work_result(work.work_item_id)
                self.assertEqual(result.attempt_id, new.session.attempt.attempt_id)
                self.assertEqual(new.enforcer.connection.execute("SELECT count(*) FROM review_markers").fetchone()[0], 1)
                self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 7)
                attempts = state["runtime"].repository.list_work_attempts(work.work_item_id)
                self.assertEqual(sum(attempt.status.value == "SUCCEEDED" for attempt in attempts), 1)
            finally:
                if new:
                    new.enforcer.close()
                fixture.close(runner, state, old)
