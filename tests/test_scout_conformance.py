import unittest

from legion_cognition import (
    InMemoryScoutRuntime,
    MissionContext,
    ScoutEvidence,
    ScoutRequest,
    ScoutResult,
    ScoutRuntimeConformance,
)
from legion_kernel import Principal, PrincipalType


class UnsafeScoutRuntime:
    """A deliberately non-conforming candidate used to prove the harness."""

    def run_scout(self, request):
        return ScoutResult(
            mission_id=request.context.mission_id,
            mission_version=request.context.mission_version,
            scout=request.scout,
            query=request.query,
            evidence=request.evidence,
            recommendation="Unsafe candidate accepted the request.",
        )


class ScoutRuntimeConformanceTests(unittest.TestCase):
    def setUp(self):
        self.request = ScoutRequest(
            context=MissionContext(
                mission_id="mission-1",
                mission_version=3,
                title="Conformance Mission",
                objective="Evaluate Scout adapters.",
                status="ACTIVE",
                roe_level="OBSERVE",
                constraints=("Read-only.",),
            ),
            scout=Principal(PrincipalType.WORKLOAD, "scout", frozenset({"MISSION_WORKER"})),
            query="Collect operational observations.",
            granted_capabilities=frozenset({"read.mission", "read.evidence"}),
            evidence=(
                ScoutEvidence(
                    source="https://example.invalid/metrics",
                    summary="A read-only observation.",
                    observed_at="2026-09-13T00:00:00Z",
                ),
            ),
        )

    def test_reference_runtime_passes_the_shared_failure_matrix(self):
        report = ScoutRuntimeConformance().evaluate(
            candidate="in-memory",
            runtime=InMemoryScoutRuntime(),
            request=self.request,
        )
        self.assertTrue(report.passed)
        self.assertEqual(
            [check.name for check in report.checks],
            ["valid_request", "missing_mission_read", "mutating_capability", "blank_query", "invalid_evidence"],
        )

    def test_harness_detects_a_runtime_that_accepts_invalid_requests(self):
        report = ScoutRuntimeConformance().evaluate(
            candidate="unsafe",
            runtime=UnsafeScoutRuntime(),
            request=self.request,
        )
        self.assertFalse(report.passed)
        failures = {check.name for check in report.checks if not check.passed}
        self.assertEqual(
            failures,
            {"missing_mission_read", "mutating_capability", "blank_query", "invalid_evidence"},
        )


if __name__ == "__main__":
    unittest.main()
