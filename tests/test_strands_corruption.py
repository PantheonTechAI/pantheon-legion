"""Corrupt/scope-mismatched restoration refuses before any new model call."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from experiments.strands.state import MAX_STORE_BYTES, OperationalStore
from legion_cognition.capability import CognitionError
from legion_runtime import RuntimeOperationError
from tests import test_strands_spike, test_strands_profiles
from tests.runtime_postgres import reset_runtime_database


@unittest.skipUnless(os.environ.get("LEGION_STRANDS_ACCEPTANCE") == "1", "opt-in real SDK snapshot producer")
class SnapshotCorruptionTests(unittest.TestCase):
    state = test_strands_spike.StrandsRuntimeTests.state
    delegate = test_strands_spike.StrandsRuntimeTests.delegate
    profile = test_strands_profiles.StrandsProfileTests.profile

    def test_real_p1_p2_snapshot_corruption_matrix(self):
        for persistence in ("P1", "P2"):
            reset_runtime_database()
            runner, state, peer, driver, root = self.profile(persistence=persistence)
            work = self.delegate(state)
            original = driver.worker.run

            def stop_before_accept(session, handler):
                original(session, handler)
                raise OSError("SYNTHETIC_CAPTURED_NOT_ACCEPTED")

            driver.worker.run = stop_before_accept
            with self.assertRaises(RuntimeOperationError):
                runner._claim_and_execute(state, work)
            path = root / work.work_item_id / "1.json"
            saved = path.read_text()
            before = len(peer.requests)
            changes = [
                lambda p: p.update(generation=2), lambda p: p.update(source_attempt_id="forged"),
                lambda p: p.update(source_execution_id="forged"), lambda p: p.update(unexpected=True),
                lambda p: p["scope"].update(schema=99), lambda p: p["scope"].update(sdk="0.0.0"),
                lambda p: p["scope"].update(config_digest="0" * 64),
                lambda p: p["scope"].update(mission_id="other-tenant-mission"),
                lambda p: p["scope"].update(agent_id="other-tenant-agent"),
                lambda p: p["scope"].update(work_item_id="other-work"),
                lambda p: p["scope"].update(assignment_id="other-assignment"),
                lambda p: p["scope"].update(binding_id="other-binding"),
                lambda p: p["scope"].update(grant_id="forged-approval"),
                lambda p: p["scope"].update(knowledge_scope={"id": "other-tenant", "version": "1.0.0"}),
                lambda p: p.update(state={"session_operational/../../escape": {}}),
            ]
            corrupt = ["{truncated", saved.replace('"generation": 1', '"generation": 1, "generation": 1'),
                       "x" * (MAX_STORE_BYTES + 1)]
            for change in changes:
                payload = json.loads(saved)
                change(payload)
                corrupt.append(json.dumps(payload))
            for index, content in enumerate(corrupt):
                with self.subTest(persistence=persistence, case=index), tempfile.TemporaryDirectory() as scratch:
                    path.write_text(content)
                    with self.assertRaises(CognitionError):
                        driver.state_store.restore(driver.session, scratch, driver.config)
                    self.assertFalse((Path(scratch) / "native").exists())
            path.write_text(saved)
            with tempfile.TemporaryDirectory() as scratch:
                self.assertTrue(driver.state_store.restore(driver.session, scratch, driver.config))
            self.assertEqual(len(peer.requests), before)
            self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))

    def test_native_schema_never_accepts_paths_or_prohibited_content(self):
        for name, value in (("../escape", {}), ("session_operational/agents/../escape", {}),
                            ("session_operational/session.json", {"x": "SECRET_SENTINEL_DO_NOT_RETAIN"}),
                            ("session_operational/session.json", {"reasoningContent": "synthetic"}),
                            ("session_operational/session.json", [])):
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                OperationalStore._validate_native(name, value)
