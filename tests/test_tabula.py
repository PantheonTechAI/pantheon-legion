import tempfile
import unittest
from pathlib import Path

from aquila_api import AquilaService, DelegationGrant
from legion_cognition import InMemoryScoutRuntime
from legion_kernel import AuthorizationError, Principal, PrincipalType, RoeLevel
from legion_tabula import InMemoryTabula, KnowledgeRecord, KnowledgeScope, SQLiteTabula


class TabulaTests(unittest.TestCase):
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
                "title": "Tabula mission",
                "objective": "Retrieve only scoped evidence.",
            },
        )
        self.mission_id = created.body["id"]
        self.tabula = InMemoryTabula()
        self.scope = KnowledgeScope(
            organization_id="11111111-1111-4111-8111-111111111111",
            workspace_id="22222222-2222-4222-8222-222222222222",
        )
        self.tabula.add(KnowledgeRecord(
            id="workspace-metrics", scope=self.scope,
            source="metrics://api", summary="API error rate increased after deployment.",
            observed_at="2026-09-13T00:00:00Z",
        ))
        self.tabula.add(KnowledgeRecord(
            id="other-workspace", scope=KnowledgeScope(
                organization_id=self.scope.organization_id,
                workspace_id="33333333-3333-4333-8333-333333333333",
            ), source="metrics://other", summary="API error rate is normal.",
            observed_at="2026-09-13T00:00:00Z",
        ))
        self.tabula.add(KnowledgeRecord(
            id="other-organization", scope=KnowledgeScope(
                organization_id="44444444-4444-4444-8444-444444444444",
            ), source="metrics://external", summary="API error rate increased.",
            observed_at="2026-09-13T00:00:00Z",
        ))
        self.tabula.add(KnowledgeRecord(
            id="other-mission", scope=KnowledgeScope(
                organization_id=self.scope.organization_id,
                workspace_id=self.scope.workspace_id,
                mission_id="55555555-5555-4555-8555-555555555555",
            ), source="metrics://other-mission", summary="API error rate increased.",
            observed_at="2026-09-13T00:00:00Z",
        ))

    def grant(self, operations=frozenset({"READ_KNOWLEDGE", "READ_MISSION"})):
        return DelegationGrant(
            grant_id="tabula-read-grant", issuer=self.owner, subject=self.scout,
            mission_id=self.mission_id, allowed_operations=operations,
            roe_ceiling=RoeLevel.OBSERVE, expires_at="9999-01-01T00:00:00Z",
        )

    def test_retrieval_filters_other_workspace_and_organization_records(self):
        results = self.service.retrieve_knowledge(
            mission_id=self.mission_id, worker=self.scout, delegation=self.grant(),
            tabula=self.tabula, query="api error",
        )
        self.assertEqual([item.record_id for item in results], ["workspace-metrics"])
        self.assertEqual(results[0].source, "metrics://api")

    def test_tabula_scout_receives_provenance_bearing_evidence(self):
        result = self.service.run_tabula_scout(
            mission_id=self.mission_id, scout=self.scout, delegation=self.grant(),
            runtime=InMemoryScoutRuntime(), tabula=self.tabula, query="api error",
            granted_capabilities=frozenset({"read.mission", "read.knowledge"}),
        )
        self.assertEqual([(item.source, item.summary) for item in result.evidence], [
            ("metrics://api", "API error rate increased after deployment."),
        ])

    def test_knowledge_retrieval_requires_its_own_delegated_operation(self):
        with self.assertRaisesRegex(AuthorizationError, "DELEGATED_OPERATION_DENIED"):
            self.service.retrieve_knowledge(
                mission_id=self.mission_id, worker=self.scout,
                delegation=self.grant(frozenset({"READ_MISSION"})),
                tabula=self.tabula, query="api error",
            )


class SQLiteTabulaTests(unittest.TestCase):
    def test_records_survive_reopen_and_preserve_scope_filtering(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "tabula.sqlite3")
            scope = KnowledgeScope(
                organization_id="11111111-1111-4111-8111-111111111111",
                workspace_id="22222222-2222-4222-8222-222222222222",
                mission_id="33333333-3333-4333-8333-333333333333",
            )
            tabula = SQLiteTabula(database)
            tabula.add(KnowledgeRecord(
                id="mission-metrics", scope=scope,
                source="metrics://api", summary="API error rate increased.",
                observed_at="2026-09-13T00:00:00Z",
            ))
            tabula.add(KnowledgeRecord(
                id="workspace-metrics", scope=KnowledgeScope(
                    organization_id=scope.organization_id, workspace_id=scope.workspace_id,
                ), source="metrics://workspace", summary="API error budget is low.",
                observed_at="2026-09-13T00:00:00Z",
            ))
            tabula.add(KnowledgeRecord(
                id="other-mission", scope=KnowledgeScope(
                    organization_id=scope.organization_id, workspace_id=scope.workspace_id,
                    mission_id="44444444-4444-4444-8444-444444444444",
                ), source="metrics://other", summary="API error rate increased.",
                observed_at="2026-09-13T00:00:00Z",
            ))
            tabula.close()

            reopened = SQLiteTabula(database)
            results = reopened.retrieve(scope=scope, query="api error")
            self.assertEqual(
                [(item.record_id, item.relevance) for item in results],
                [("mission-metrics", 2), ("workspace-metrics", 2)],
            )
            with self.assertRaisesRegex(ValueError, "KNOWLEDGE_RECORD_DUPLICATE"):
                reopened.add(KnowledgeRecord(
                    id="mission-metrics", scope=scope,
                    source="metrics://duplicate", summary="Duplicate.",
                    observed_at="2026-09-13T00:00:00Z",
                ))
            reopened.close()


if __name__ == "__main__":
    unittest.main()
