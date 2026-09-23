"""Live smoke proof and side-effect gates, without Docker or provider calls."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from legion_cognition.capability import CognitionError
from tests.acceptance import strands_live as live


def evidence():
    return dict(seed={"review_code": "PRIVATE_RANDOM_CODE", "record_id": "allowed", "content_digest": "digest"},
        result=NS(summary="Aquila owns Mission authority: PRIVATE_RANDOM_CODE", result_id="result",
                  content_digest="result-digest", evidence_references=("ref",)),
        references=[NS(external_record_id="allowed", evidence_reference_id="ref", tabula_audit_correlation_id="audit")],
        trial=NS(model_calls=2, retrievals=1, trace_id="trace", execution_id="execution", selection={"catalog_revision": "fresh"}),
        operations=[NS(kind="MODEL", status="SUCCESS", facts={"decision_id": decision, "finish_reason": finish,
            "prompt_tokens": 1, "completion_tokens": 2, "reasoning_tokens": 1, "latency_ms": 3})
            for decision, finish in (("decision1", "tool_calls"), ("decision2", "stop"))],
        telemetry=[{"trace_id": "trace"}], knowledge_decisions=["k1", "k2", "k3"])


class StrandsLiveTests(unittest.TestCase):
    def test_proof_is_content_safe(self):
        report = live.check_result(**evidence())
        self.assertEqual(report["model_calls"], 2)
        self.assertTrue(report["review_code_matched"])
        self.assertNotIn("PRIVATE_RANDOM_CODE", json.dumps(report))

    def test_false_success_is_rejected(self):
        mutations = [
            lambda v: setattr(v["result"], "summary", "Aquila guessed a code"),
            lambda v: setattr(v["result"], "summary", "PRIVATE_RANDOM_CODE OUT_OF_SCOPE_CONTROL Aquila"),
            lambda v: setattr(v["references"][0], "external_record_id", "control"),
            lambda v: setattr(v["result"], "evidence_references", ("forged",)),
            lambda v: v.update(references=[]),
            lambda v: setattr(v["trial"], "model_calls", 3),
            lambda v: v["operations"][1].facts.update(decision_id="decision1"),
            lambda v: v["operations"][1].facts.update(finish_reason="length"),
            lambda v: setattr(v["operations"][0], "status", "FAILED"),
            lambda v: v["operations"].append(NS(kind="RETRIEVAL", status="FAILED")),
            lambda v: v["operations"].append(NS(kind="ACTION", status="SUCCESS")),
            lambda v: v.update(knowledge_decisions=["k1", "k1", "k3"]),
            lambda v: v.update(telemetry=[]),
            lambda v: v["telemetry"][0].update(trace_id="other"),
        ]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                values = evidence()
                mutation(values)
                with self.assertRaises(CognitionError):
                    live.check_result(**values)

    def arguments(self, report):
        return ["--config", "/not-read", "--tabula-root", "/not-used", "--env-file", "/not-read",
                "--project-name", "pantheon-federation-unit", "--report", str(report)]

    def test_each_missing_acknowledgement_refuses_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            flags = ["--execute", "--reset-test-database", "--acknowledge-cleartext", "--acknowledge-unauthenticated"]
            for omitted in flags:
                with self.subTest(omitted=omitted), patch.object(live, "runtime_test_database_url") as database, \
                        redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        live.main(self.arguments(report) + [flag for flag in flags if flag != omitted])
                    database.assert_not_called()
                    self.assertFalse(report.exists())

    def test_preflight_failure_is_private_and_never_resets_database(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            argv = self.arguments(report) + ["--execute", "--reset-test-database",
                "--acknowledge-cleartext", "--acknowledge-unauthenticated"]
            with patch.object(live, "runtime_test_database_url", side_effect=ValueError("PRIVATE_SECRET")), \
                    patch.object(live, "reset_runtime_database") as reset, redirect_stdout(io.StringIO()):
                self.assertEqual(live.main(argv), 1)
                reset.assert_not_called()
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("PRIVATE_SECRET", report.read_text())
            self.assertEqual(json.loads(report.read_text())["status"], "FAIL")
            with self.assertRaises(FileExistsError):
                live.main(argv)

    def test_symlink_report_is_never_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target"
            target.write_text("preserve")
            report = Path(directory) / "report"
            report.symlink_to(target)
            argv = self.arguments(report) + ["--execute", "--reset-test-database",
                "--acknowledge-cleartext", "--acknowledge-unauthenticated"]
            with self.assertRaises(FileExistsError):
                live.main(argv)
            self.assertEqual(target.read_text(), "preserve")

    def test_trial_and_cleanup_failures_never_report_pass(self):
        for cleanup_fails in (False, True):
            with self.subTest(cleanup_fails=cleanup_fails), tempfile.TemporaryDirectory() as directory:
                report = Path(directory) / "report.json"
                argv = self.arguments(report) + ["--execute", "--reset-test-database",
                    "--acknowledge-cleartext", "--acknowledge-unauthenticated"]
                with patch.object(live, "runtime_test_database_url"), patch.object(live, "load_catalog"), \
                        patch.object(live, "CognitionTabulaStack") as stack, patch.object(live, "FixtureSTSServer"), \
                        patch.object(live, "reset_runtime_database"), patch.object(live, "execute_trial") as execute, \
                        redirect_stdout(io.StringIO()):
                    execute.side_effect = CognitionError("COGNITION_NO_MATCH")
                    if cleanup_fails:
                        stack.return_value.cleanup.side_effect = OSError("PRIVATE_FAILURE")
                    self.assertEqual(live.main(argv), 1)
                    stack.return_value.cleanup.assert_called_once()
                value = json.loads(report.read_text())
                self.assertEqual(value["status"], "FAIL")
                self.assertEqual(value["disposable_stack_removed"], not cleanup_fails)
                self.assertEqual(value["error_code"], "STRANDS_LIVE_FAILED" if cleanup_fails else "COGNITION_NO_MATCH")
                self.assertNotIn("PRIVATE_FAILURE", report.read_text())
