"""Measurement scheduling and honest failure denominators; no live calls."""

from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.acceptance.strands_comparison import configure_live, main, safe_code, schedule, summarize


class ComparisonProtocolTests(unittest.TestCase):
    def test_long_live_run_issues_fresh_short_lived_tokens_not_fixed_clock_expiry(self):
        now = datetime.now(timezone.utc)
        sts = Mock(current_time=now - timedelta(minutes=10))
        def advance(delta):
            sts.current_time += delta
        sts.advance.side_effect = advance
        with patch("tests.acceptance.strands_comparison.configured_cognition"), patch(
            "tests.acceptance.strands_comparison.InProcessAquilaKnowledgeAuthority"
        ) as authority:
            configure_live({"runtime": SimpleNamespace(), "aquila": Mock()}, "unused",
                           SimpleNamespace(mcp_endpoint="http://127.0.0.1:1/mcp"), sts)
            issue = authority.call_args.args[1]
            original = {"mission_id": "unchanged", "issued_at": "historical", "expires_at": "historical"}
            issue(original)
            claims = sts.issue_token.call_args.args[0]
            issued = datetime.fromisoformat(claims["issued_at"].replace("Z", "+00:00"))
            expiry = datetime.fromisoformat(claims["expires_at"].replace("Z", "+00:00"))
            self.assertGreaterEqual(issued, now)
            self.assertEqual(expiry - issued, timedelta(minutes=5))
            self.assertEqual(claims["mission_id"], "unchanged")
            self.assertEqual(original["expires_at"], "historical")

    def test_five_alternating_pairs_per_profile_and_every_novel_profile(self):
        samples = schedule()
        self.assertEqual(len(samples), 46)
        for persistence in ("P0", "P1", "P2"):
            for repetition in range(5):
                pair = persistence + "-" + str(repetition + 1)
                values = [sample for sample in samples if sample["pair_id"] == pair]
                expected = ["B0", "strands"] if repetition % 2 == 0 else ["strands", "B0"]
                self.assertEqual([value["implementation"] for value in values], expected)
        self.assertEqual(sum(s["scenario"] == "comparison" for s in samples), 30)
        self.assertEqual(sum(s["scenario"] == "orchestration" for s in samples), 6)
        self.assertEqual(sum(s["scenario"] == "worker_recovery" for s in samples), 9)
        self.assertEqual(sum(s["scenario"] == "effect_recovery" for s in samples), 1)

    def test_failures_remain_in_denominator_and_are_not_latency_zero(self):
        metrics = dict(elapsed_ms=10, provider_ms=8, non_provider_ms=2, prompt_tokens=20,
                       completion_tokens=5, model_calls=2, snapshot_bytes=0)
        common = dict(scenario="comparison", implementation="B0", persistence="NONE", paired_persistence="P2")
        result = summarize([{**common, "status": "PASS", **metrics}, {**common, "status": "FAIL"}])["B0/P2"]
        self.assertEqual((result["total"], result["passed"], result["failed"]), (2, 1, 1))
        self.assertEqual(result["metrics"]["elapsed_ms"], {"median": 10, "minimum": 10, "maximum": 10})
        self.assertIsNone(summarize([{**common, "status": "FAIL"}])["B0/P2"]["metrics"]["elapsed_ms"])

    def test_error_text_never_becomes_report_content(self):
        self.assertEqual(safe_code(ValueError("Bearer private")), "LIVE_SAMPLE_FAILED")
        error = ValueError()
        error.code = "PRIVATE secret text"
        self.assertEqual(safe_code(error), "LIVE_SAMPLE_FAILED")

    def test_effect_approval_acknowledgement_is_separate(self):
        args = ["--config", "unused", "--tabula-root", "unused", "--env-file", "unused",
                "--output", "unused", "--project-name", "pantheon-federation-test", "--suite", "effect",
                "--execute", "--reset-test-database", "--acknowledge-cleartext", "--acknowledge-unauthenticated"]
        with patch("tests.acceptance.strands_comparison.runtime_test_database_url") as database, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(args)
            database.assert_not_called()
