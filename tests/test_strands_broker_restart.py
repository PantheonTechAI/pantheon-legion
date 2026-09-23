"""Kill actual broker processes; reconstruct from the actual owner databases."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

from tests.acceptance.strands_restart import cleanup_orphans
from tests.cognition_http import inference_server, tool_response, final_response
from tests.runtime_postgres import reset_runtime_database
from tests.test_strands_actions import action_response


@unittest.skipUnless(os.environ.get("LEGION_STRANDS_ACCEPTANCE") == "1", "opt-in broker kill acceptance")
class BrokerRestartTests(unittest.TestCase):
    def test_hard_broker_kill_preserves_authority_effects_budgets_and_identity(self):
        for case in ("approval", "effect", "admission", "P0", "P1", "P2"):
            with self.subTest(case=case):
                reset_runtime_database()
                action = case in {"approval", "effect"}
                responses = ([tool_response(), action_response()] if action else [tool_response(), final_response()])
                if case == "effect":
                    responses += [tool_response(), action_response()]
                with inference_server(responses) as peer, tempfile.TemporaryDirectory(prefix="legion-broker-restart-") as directory:
                    root = Path(directory)
                    command = [sys.executable, "-m", "tests.acceptance.strands_restart",
                        "kill", "--case", case, "--root", directory, "--origin", peer.origin, "--acknowledge-test-state"]
                    try:
                        killed = subprocess.run(command, capture_output=True, timeout=120)
                        self.assertEqual(killed.returncode, -signal.SIGKILL, killed.stderr.decode())
                        checkpoint = json.loads((root / "checkpoint.json").read_text())
                        self.assertIsNone(checkpoint["result_id"])
                        self.assertEqual(checkpoint["effect_count"], int(case == "effect"))
                        if case == "approval":
                            self.assertEqual(checkpoint["approvals"][0]["status"], "PENDING")
                        old_calls = checkpoint["trial"]["model_calls"]
                        physical_before = sum(body is not None for _, body, _ in peer.requests)
                        self.assertEqual(physical_before, old_calls - int(case == "admission"))
                        cleanup_orphans(root)
                        peer.responses[:] = [tool_response()] + ([action_response()] if action else []) + [final_response()]
                        command[3] = "resume"
                        resumed = subprocess.run(command, capture_output=True, timeout=120)
                        self.assertEqual(resumed.returncode, 0, resumed.stderr.decode())
                        recovered = json.loads((root / "recovered.json").read_text())
                        before, after = recovered["before"], recovered["after"]
                        for field in ("agent_id", "work_item_id", "mission_id"):
                            self.assertEqual(checkpoint[field], after[field])
                        self.assertEqual(before["trial"], checkpoint["trial"])
                        self.assertEqual(after["trial"]["logical_operation_id"], checkpoint["trial"]["logical_operation_id"])
                        self.assertNotEqual(after["trial"]["execution_id"], checkpoint["trial"]["execution_id"])
                        self.assertNotEqual(after["trial"]["active_attempt_id"], checkpoint["trial"]["active_attempt_id"])
                        self.assertEqual(after["trial"]["model_calls"], old_calls + (3 if action else 2))
                        self.assertEqual(after["effect_count"], int(action))
                        if case == "effect":
                            self.assertEqual(after["receipt_ids"], checkpoint["receipt_ids"])
                        if action:
                            self.assertEqual(after["approvals"][0]["status"], "CONSUMED")
                        self.assertIsNotNone(after["result_id"])
                        self.assertEqual(after["restored"], case in {"P1", "P2"})
                        self.assertEqual(sum(item["status"] == "SUCCEEDED" for item in after["attempts"]), 1)
                        if case == "admission":
                            old = [op for op in after["operations"] if op["attempt_id"] == checkpoint["trial"]["active_attempt_id"]]
                            self.assertEqual(old[0]["status"], "PREPARED")
                            self.assertEqual(after["attempts"][0]["status"], "ABANDONED")
                        safe = json.dumps(recovered)
                        self.assertNotIn("EXPLICIT_REASONING_SENTINEL_DO_NOT_RETAIN", safe)
                    finally:
                        cleanup_orphans(root)
