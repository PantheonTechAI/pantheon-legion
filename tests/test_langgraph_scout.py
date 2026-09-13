import unittest

from legion_cognition import (
    LangGraphScoutRuntime,
    MissionContext,
    ScoutEvidence,
    ScoutRequest,
    ScoutRuntimeConformance,
)
from legion_kernel import Principal, PrincipalType


class RecordingResponder:
    def __init__(self):
        self.calls = []

    def recommend(self, *, context, query, evidence):
        self.calls.append((context, query, evidence))
        return f"Investigate {len(evidence)} scoped observation(s) for: {query}"


class LangGraphScoutRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.request = ScoutRequest(
            context=MissionContext(
                mission_id="mission-1", mission_version=3,
                title="LangGraph Mission", objective="Evaluate the runtime.",
                status="ACTIVE", roe_level="OBSERVE", constraints=("Read-only.",),
            ),
            scout=Principal(PrincipalType.WORKLOAD, "scout", frozenset({"MISSION_WORKER"})),
            query="Investigate API errors.",
            granted_capabilities=frozenset({"read.mission", "read.knowledge"}),
            evidence=(ScoutEvidence(
                source="metrics://api", summary="Error rate increased.",
                observed_at="2026-09-13T00:00:00Z",
            ),),
        )

    def test_langgraph_runtime_passes_the_scout_conformance_matrix(self):
        report = ScoutRuntimeConformance().evaluate(
            candidate="langgraph",
            runtime=LangGraphScoutRuntime(RecordingResponder()),
            request=self.request,
        )
        self.assertTrue(report.passed)

    def test_responder_receives_only_bounded_scout_inputs(self):
        responder = RecordingResponder()
        result = LangGraphScoutRuntime(responder).run_scout(self.request)
        self.assertIn("1 scoped observation", result.recommendation)
        self.assertEqual(responder.calls, [(self.request.context, self.request.query, self.request.evidence)])


if __name__ == "__main__":
    unittest.main()
