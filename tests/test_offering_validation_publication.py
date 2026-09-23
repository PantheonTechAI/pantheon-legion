"""Publication fault windows and explicit operator handoff invariants."""

import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from legion_cognition.capability import CognitionError
from legion_cognition import offering_validation
from legion_cognition.offering_validation import ValidationBundle
from tests.cognition_http import inference_server
from tests import test_offering_validation as fixtures
from tests.test_offering_validation import initial_response, continuation


class OfferingPublicationTests(unittest.TestCase):
    def test_cli_trust_failure_precedes_database_reset_and_output_creation(self):
        import contextlib
        import io
        from tests.acceptance import validate_offering as cli
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "candidate.json"
            source.write_text(json.dumps(fixtures.candidate_config("http://127.0.0.1:8000")))
            before = source.read_bytes()
            output = io.StringIO()
            with patch.object(cli, "runtime_test_database_url"), patch.object(cli, "reset_runtime_database") as reset, \
                    patch.object(cli.VllmSshObserver, "observe", side_effect=CognitionError("VALIDATION_OBSERVATION_UNAVAILABLE")), \
                    contextlib.redirect_stdout(output):
                status = cli.main(["--candidate", str(source), "--output", str(root / "bundle"),
                    "--ssh-host", "127.0.0.1", "--ssh-user", "jtdauria", "--container", "vllm-server",
                    "--execute", "--reset-test-database", "--acknowledge-cleartext", "--acknowledge-unauthenticated"])
            self.assertEqual(status, 1)
            reset.assert_not_called()
            self.assertFalse((root / "bundle").exists())
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(json.loads(output.getvalue())["error_code"], "VALIDATION_OBSERVATION_UNAVAILABLE")

    def test_each_publication_interruption_keeps_final_catalog_absent(self):
        for stage in ("report", "pending", "final_guard", "link", "stale", "commit_sync"):
            with self.subTest(stage=stage), inference_server([initial_response(), continuation]) as peer, tempfile.TemporaryDirectory() as directory:
                validator, ports = fixtures.OfferingValidationTests().setup_run(peer)
                validator.evaluate(**ports)
                bundle = ValidationBundle(Path(directory) / "bundle")
                result = SimpleNamespace(result_id=str(uuid4()), work_item_id=ports["context"].work_item_id,
                    attempt_id=ports["context"].attempt_id, content_digest="a" * 64)
                calls = 0
                def guard():
                    nonlocal calls
                    calls += 1
                    if stage == "final_guard" and calls == 2:
                        raise CognitionError("COGNITION_AUTHORITY_DENIED")
                original = bundle.write
                def write(name, value):
                    if (stage == "report" and name == "report.json") or (stage == "pending" and name == ".catalog.pending"):
                        raise OSError("simulated write failure")
                    original(name, value)
                if stage == "stale":
                    from datetime import timedelta
                    from legion_cognition.offering_validation import utcnow
                    validator.clock = lambda: utcnow() + timedelta(minutes=2)
                original_sync = os.fsync
                def sync(fd):
                    if stage == "commit_sync" and (bundle.root / "catalog.json").exists():
                        raise OSError("simulated commit sync failure")
                    original_sync(fd)
                try:
                    with patch.object(bundle, "write", write), patch("os.fsync", sync), patch("os.link", side_effect=OSError("simulated link failure")) if stage == "link" else patch("os.link", wraps=os.link):
                        with self.assertRaises((OSError, CognitionError)):
                            bundle.publish(validator, accepted_result=result, guard=guard)
                    self.assertFalse((bundle.root / "catalog.json").exists())
                    if (bundle.root / "report.json").exists():
                        self.assertEqual(json.loads((bundle.root / "report.json").read_text())["status"], "PROBES_PASSED")
                finally:
                    bundle.close()

    def test_publication_never_overwrites_an_occupied_catalog_or_changes_environment(self):
        with inference_server([initial_response(), continuation]) as peer, tempfile.TemporaryDirectory() as directory:
            validator, ports = fixtures.OfferingValidationTests().setup_run(peer)
            validator.evaluate(**ports)
            bundle = ValidationBundle(Path(directory) / "bundle")
            try:
                target = bundle.root / "catalog.json"
                target.write_text("PRESERVE_EXISTING")
                result = SimpleNamespace(result_id=str(uuid4()), work_item_id=ports["context"].work_item_id,
                    attempt_id=ports["context"].attempt_id, content_digest="a" * 64)
                before = dict(os.environ)
                example = Path("deploy/cognition.example.json").read_bytes()
                with self.assertRaises(FileExistsError):
                    bundle.publish(validator, accepted_result=result, guard=lambda: None)
                self.assertEqual(target.read_text(), "PRESERVE_EXISTING")
                self.assertEqual(dict(os.environ), before)
                self.assertEqual(Path("deploy/cognition.example.json").read_bytes(), example)
            finally:
                bundle.close()

    def test_validator_does_not_import_router_or_retrying_invoker(self):
        tree = ast.parse(Path(offering_validation.__file__).read_text())
        names = {alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
        self.assertFalse(names & {"CognitionRouter", "AuthorizedCognitionInvoker"})
