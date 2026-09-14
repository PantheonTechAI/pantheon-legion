import unittest

from aquila_api import AquilaService
from legion_cognition import InMemoryScoutRuntime, ReadOnlyScoutError, ScoutEvidence
from legion_kernel import AuthorizationError, Principal, PrincipalType, RoeLevel


class ScoutRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.service = AquilaService()
        self.owner = Principal(
            PrincipalType.HUMAN, "owner", frozenset({"MISSION_OWNER", "OPERATOR"})
        )
        self.scout = Principal(
            PrincipalType.WORKLOAD, "scout", frozenset({"MISSION_WORKER"})
        )
        created = self.service.create_mission(
            actor=self.owner,
            body={
                "organization_id": "11111111-1111-4111-8111-111111111111",
                "workspace_id": "22222222-2222-4222-8222-222222222222",
                "title": "Scout mission",
                "objective": "Collect read-only evidence.",
            },
        )
        self.mission_id = created.body["id"]

    def grant(self, *, operations=frozenset({"READ_MISSION"})):
        return self.service.issue_delegation(
            issuer=self.owner, subject=self.scout, mission_id=self.mission_id,
            allowed_operations=operations, roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )

    def test_scout_receives_bounded_context_and_does_not_mutate_mission(self):
        before = self.service.get_mission(actor=self.owner, mission_id=self.mission_id).body
        timeline_before = self.service.get_timeline(actor=self.owner, mission_id=self.mission_id).body

        result = self.service.run_scout(
            mission_id=self.mission_id,
            scout=self.scout,
            delegation_id=self.grant(),
            runtime=InMemoryScoutRuntime(),
            query="Find relevant observations.",
            granted_capabilities=frozenset({"read.mission", "read.evidence"}),
            evidence=(
                ScoutEvidence(
                    source="https://example.invalid/metrics",
                    summary="Error rate increased after deployment.",
                    observed_at="2026-09-13T00:00:00Z",
                ),
            ),
        )

        self.assertEqual(result.mission_id, self.mission_id)
        self.assertEqual(result.mission_version, before["version"])
        self.assertEqual(result.scout, self.scout)
        self.assertEqual(len(result.evidence), 1)
        self.assertIn("1 observation", result.recommendation)
        self.assertEqual(
            self.service.get_mission(actor=self.owner, mission_id=self.mission_id).body,
            before,
        )
        events = self.service.get_timeline(actor=self.owner, mission_id=self.mission_id).body["events"]
        self.assertGreater(len(events), len(timeline_before["events"]))
        self.assertEqual(events[-1]["event_type"], "DELEGATION_EVALUATED")

    def test_scout_requires_bounded_workload_delegation(self):
        with self.assertRaisesRegex(AuthorizationError, "DELEGATION_REQUIRED"):
            self.service.run_scout(
                mission_id=self.mission_id,
                scout=self.scout,
            delegation_id=None,
                runtime=InMemoryScoutRuntime(),
                query="Collect observations.",
                granted_capabilities=frozenset({"read.mission"}),
            )

        with self.assertRaisesRegex(AuthorizationError, "DELEGATED_OPERATION_DENIED"):
            self.service.run_scout(
                mission_id=self.mission_id,
                scout=self.scout,
                delegation_id=self.grant(operations=frozenset({"EXECUTE_ACTION"})),
                runtime=InMemoryScoutRuntime(),
                query="Collect observations.",
                granted_capabilities=frozenset({"read.mission"}),
            )

    def test_scout_rejects_any_non_read_capability(self):
        with self.assertRaisesRegex(ReadOnlyScoutError, "SCOUT_CAPABILITY_DENIED"):
            self.service.run_scout(
                mission_id=self.mission_id,
                scout=self.scout,
                delegation_id=self.grant(),
                runtime=InMemoryScoutRuntime(),
                query="Collect observations.",
                granted_capabilities=frozenset({"read.mission", "write.production"}),
            )


if __name__ == "__main__":
    unittest.main()
