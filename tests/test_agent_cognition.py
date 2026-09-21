import unittest

from legion_cognition import (
    InMemoryScoutRuntime,
    LegacyScoutRuntimeBridge,
    ScoutEvidence,
    ScoutResult,
)
from legion_runtime import (
    AgentEvidence,
    AgentCognitionRequest,
    AgentMissionContext,
    AgentRole,
    CognitionRejected,
    WorkItem,
    WorkResult,
    WorkStatus,
    result_digest,
)


class AgentCognitionContractTests(unittest.TestCase):
    def _request(self, **overrides):
        values = {
            "request_id": "11111111-1111-4111-8111-111111111111",
            "agent_id": "22222222-2222-4222-8222-222222222222",
            "agent_role": AgentRole.SCOUT,
            "workload_subject": "scout-workload",
            "work_item_id": "33333333-3333-4333-8333-333333333333",
            "attempt_id": "11111111-1111-4111-8111-111111111111",
            "mission_id": "44444444-4444-4444-8444-444444444444",
            "mission_version": 2,
            "logical_capability": "read_only_analysis",
            "objective": "Inspect Mission state",
            "required_capabilities": ("read_only_analysis",),
            "context": AgentMissionContext(
                mission_id="44444444-4444-4444-8444-444444444444",
                mission_version=2,
                status="ACTIVE",
                title="Mission",
                objective="Objective",
                roe_level="SUPERVISED",
                constraints=("Read only",),
            ),
        }
        values.update(overrides)
        return AgentCognitionRequest(**values)

    def test_legacy_bridge_preserves_canonical_identity(self):
        bridge = LegacyScoutRuntimeBridge(InMemoryScoutRuntime())
        request = self._request()
        result = bridge.run(request)
        self.assertEqual(result.request_id, request.request_id)
        self.assertEqual(result.agent_id, request.agent_id)
        self.assertEqual(result.work_item_id, request.work_item_id)
        self.assertEqual(result.attempt_id, request.attempt_id)
        self.assertEqual(result.mission_id, request.mission_id)

    def test_legacy_bridge_rejects_mutating_capability(self):
        bridge = LegacyScoutRuntimeBridge(InMemoryScoutRuntime())
        with self.assertRaisesRegex(CognitionRejected, "CAPABILITY_DENIED"):
            bridge.run(
                self._request(
                    logical_capability="write.production",
                    required_capabilities=("write.production",),
                )
            )

    def test_grounded_bridge_round_trips_runtime_reference_ids(self):
        evidence = AgentEvidence(
            reference_id="55555555-5555-4555-8555-555555555555",
            record_id="record-one",
            revision="rev-1",
            canonical_uri="tabula://corpus/record-one/rev-1",
            content="bounded evidence",
            retrieved_at="2026-09-18T00:01:00Z",
        )
        request = self._request(
            logical_capability="grounded_corpus_analysis",
            required_capabilities=("read_only_analysis", "tabula_corpus_read"),
            evidence=(evidence,),
        )
        result = LegacyScoutRuntimeBridge(InMemoryScoutRuntime()).run(request)
        self.assertEqual(result.evidence_references, (evidence.reference_id,))

    def test_grounded_bridge_rejects_out_of_set_legacy_citation(self):
        class WrongCitationRuntime:
            def run_scout(self, request):
                return ScoutResult(
                    mission_id=request.context.mission_id,
                    mission_version=request.context.mission_version,
                    scout=request.scout,
                    query=request.query,
                    evidence=(
                        ScoutEvidence(
                            source="66666666-6666-4666-8666-666666666666",
                            summary="not supplied",
                            observed_at="2026-09-18T00:01:00Z",
                        ),
                    ),
                    recommendation="invalid citation",
                )

        evidence = AgentEvidence(
            reference_id="55555555-5555-4555-8555-555555555555",
            record_id="record-one",
            revision="rev-1",
            canonical_uri="tabula://corpus/record-one/rev-1",
            content="bounded evidence",
            retrieved_at="2026-09-18T00:01:00Z",
        )
        with self.assertRaisesRegex(
            CognitionRejected, "COGNITION_EVIDENCE_REFERENCES_INVALID"
        ):
            LegacyScoutRuntimeBridge(WrongCitationRuntime()).run(
                self._request(
                    logical_capability="grounded_corpus_analysis",
                    required_capabilities=(
                        "read_only_analysis",
                        "tabula_corpus_read",
                    ),
                    evidence=(evidence,),
                )
            )

    def test_work_content_uses_utf8_byte_bounds_and_matching_digest(self):
        with self.assertRaisesRegex(ValueError, "4096 UTF-8 bytes"):
            WorkItem(
                work_item_id="11111111-1111-4111-8111-111111111111",
                mission_id="22222222-2222-4222-8222-222222222222",
                centurion_agent_id="33333333-3333-4333-8333-333333333333",
                centurion_assignment_id="44444444-4444-4444-8444-444444444444",
                scout_agent_id="55555555-5555-4555-8555-555555555555",
                scout_assignment_id="66666666-6666-4666-8666-666666666666",
                objective="é" * 2049,
                required_capabilities=("read_only_analysis",),
                status=WorkStatus.QUEUED,
                version=1,
                correlation_id="77777777-7777-4777-8777-777777777777",
                causation_id=None,
                created_at="2026-09-18T00:00:00Z",
                updated_at="2026-09-18T00:00:00Z",
            )
        digest = result_digest("summary", ("evidence:one",))
        result = WorkResult(
            result_id="11111111-1111-4111-8111-111111111111",
            work_item_id="22222222-2222-4222-8222-222222222222",
            attempt_id="33333333-3333-4333-8333-333333333333",
            scout_agent_id="44444444-4444-4444-8444-444444444444",
            scout_binding_id="55555555-5555-4555-8555-555555555555",
            mission_version=2,
            summary="summary",
            evidence_references=("evidence:one",),
            content_digest=digest,
            produced_at="2026-09-18T00:00:00Z",
        )
        self.assertEqual(result.content_digest, digest)
        with self.assertRaisesRegex(ValueError, "does not match"):
            WorkResult(
                **{**result.__dict__, "content_digest": "0" * 64}
            )


if __name__ == "__main__":
    unittest.main()
