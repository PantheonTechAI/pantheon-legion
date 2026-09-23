"""Filesystem ownership/retention tests without model or database dependencies."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from experiments.strands.state import OperationalStore
from legion_cognition.capability import CognitionError


class OperationalStoreTests(unittest.TestCase):
    def test_nonowned_nonempty_root_refused_without_permission_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.chmod(0o755)
            (root / "unrelated").write_text("synthetic")
            with self.assertRaisesRegex(ValueError, "SPIKE_STATE_ROOT_NOT_EMPTY"):
                OperationalStore(root)
            self.assertEqual(root.stat().st_mode & 0o777, 0o755)
            self.assertEqual((root / "unrelated").read_text(), "synthetic")

    def test_symlink_root_and_worker_native_root_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            private = base / "private"
            private.mkdir()
            link = base / "linked"
            link.symlink_to(private, target_is_directory=True)
            with self.assertRaises(ValueError):
                OperationalStore(link)
            store = OperationalStore(private, synthetic=True)
            worker = base / "worker"
            worker.mkdir()
            (worker / "native").symlink_to(private, target_is_directory=True)
            with self.assertRaisesRegex(CognitionError, "SPIKE_SNAPSHOT_SYMLINK"):
                store.capture(SimpleNamespace(guard=lambda: None), worker, {"persistence": "P2"})

    def test_expired_owned_trials_deleted_and_unexpired_store_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OperationalStore(directory)
            trial = Path(directory) / str(uuid4())
            trial.mkdir()
            (trial / "1.json").write_text("synthetic")
            with self.assertRaisesRegex(CognitionError, "NOT_EXPIRED"):
                store.expire()
            with patch("experiments.strands.state.datetime") as clock:
                clock.now.return_value = datetime.now(timezone.utc) + timedelta(hours=25)
                clock.fromisoformat = datetime.fromisoformat
                self.assertEqual(store.expire(), 1)
            self.assertFalse(trial.exists())
            self.assertTrue((Path(directory) / ".legion-strands-store.json").is_file())

    def test_cleanup_validates_all_targets_before_deleting_any(self):
        with tempfile.TemporaryDirectory() as directory:
            store = OperationalStore(directory)
            trial = Path(directory) / str(uuid4())
            trial.mkdir()
            outside = Path(directory) / "unrelated"
            outside.mkdir()
            with patch("experiments.strands.state.datetime") as clock:
                clock.now.return_value = datetime.now(timezone.utc) + timedelta(hours=25)
                clock.fromisoformat = datetime.fromisoformat
                with self.assertRaises((CognitionError, ValueError)):
                    store.expire()
            self.assertTrue(trial.exists())
            self.assertTrue(outside.exists())
