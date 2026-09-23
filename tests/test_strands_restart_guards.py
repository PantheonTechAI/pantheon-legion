"""Negative controls for destructive cleanup and restart-evidence assertions."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from tests.acceptance.strands_restart import cleanup_orphans, write_private
from tests.acceptance.strands_postgres_restart import main


class RestartGuardTests(unittest.TestCase):
    def test_cleanup_refuses_malformed_or_symlinked_manifest_without_deleting(self):
        for case in ("symlink", "invalid_uuid", "wrong_name", "unknown_field"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as root:
                root = Path(root)
                execution = str(uuid4())
                record = {"execution_id": execution, "name": "legion-strands-" + execution,
                          "channel": "/tmp/legion-strands-channel-not-owned"}
                if case == "invalid_uuid":
                    record["execution_id"] = "invalid"
                elif case == "wrong_name":
                    record["name"] = "unrelated"
                elif case == "unknown_field":
                    record["extra"] = True
                if case == "symlink":
                    write_private(root / "outside.json", record)
                    (root / "workers.jsonl").symlink_to(root / "outside.json")
                else:
                    write_private(root / "workers.jsonl", record)
                with patch("tests.acceptance.strands_restart.shutil.rmtree") as remove, patch(
                    "tests.acceptance.strands_restart.DockerWorker.stop_owned"
                ) as stop:
                    with self.assertRaises(ValueError):
                        cleanup_orphans(root)
                    remove.assert_not_called()
                    stop.assert_not_called()

    def test_cleanup_refuses_unowned_channel_and_preserves_sibling(self):
        for case in ("symlink", "wrong_owner", "wrong_mode", "outside_prefix"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory(
                prefix="legion-strands-channel-"
            ) as channel:
                root, channel = Path(root), Path(channel)
                write_private(channel / "keep.json", {"preserve": True})
                target = channel
                if case == "symlink":
                    target = root / "link"
                    target.symlink_to(channel, target_is_directory=True)
                elif case == "wrong_mode":
                    channel.chmod(0o755)
                elif case == "outside_prefix":
                    target = root
                execution = str(uuid4())
                write_private(root / "workers.jsonl", {"execution_id": execution,
                    "name": "legion-strands-" + execution, "channel": str(target)})
                with ExitStack() as guards:
                    remove = guards.enter_context(patch("tests.acceptance.strands_restart.shutil.rmtree"))
                    guards.enter_context(patch("tests.acceptance.strands_restart.DockerWorker.stop_owned"))
                    if case == "wrong_owner":
                        guards.enter_context(patch("tests.acceptance.strands_restart.os.getuid", return_value=os.getuid() + 1))
                    with self.assertRaisesRegex(ValueError, "FIXTURE_CHANNEL_REFUSED"):
                        cleanup_orphans(root)
                    remove.assert_not_called()
                self.assertTrue((channel / "keep.json").is_file())
                self.assertTrue((root / "workers.jsonl").is_file())

    def test_database_verifier_rejects_drift_or_unchanged_server_before_publication(self):
        before = {"postmaster_started": "before", "facts": {"work_item_id": "work", "calls": 2}}
        for case, after, code in (
            ("drift", {"postmaster_started": "after", "facts": {"work_item_id": "work", "calls": 0}},
             "POSTGRES_SPIKE_FACTS_CHANGED"),
            ("not_restarted", before, "POSTGRES_PROCESS_NOT_RESTARTED"),
        ):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_private(root / "before.json", before)
                store = Mock()
                with patch("tests.acceptance.strands_postgres_restart.new_runtime_store", return_value=store), patch(
                    "tests.acceptance.strands_postgres_restart.evidence", return_value=after
                ), patch("tests.acceptance.strands_postgres_restart.write_private") as publish:
                    with self.assertRaisesRegex(ValueError, code):
                        main(["verify", "--before", str(root / "before.json"), "--after", str(root / "after.json"),
                              "--acknowledge-test-database"])
                    publish.assert_not_called()
                    store.close.assert_called_once()
                self.assertFalse((root / "after.json").exists())
                self.assertEqual(json.loads((root / "before.json").read_text()), before)
