import json
import unittest

from aquila_api import AquilaService
from legion_kernel import AuthorizationError, Principal, PrincipalType, RoeLevel
from legion_tabula import McpResponse, ScopeBinding, TabulaCorpusClient


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
BINDING_ID = "33333333-3333-4333-8333-333333333333"
CORRELATION_ID = "44444444-4444-4444-8444-444444444444"
TABULA_AUDIT_ID = "55555555-5555-4555-8555-555555555555"


class FederatedCorpusAuditTests(unittest.TestCase):
    def setUp(self):
        self.service = AquilaService()
        self.owner = Principal(PrincipalType.HUMAN, "owner", frozenset({"MISSION_OWNER", "OPERATOR"}))
        self.worker = Principal(PrincipalType.WORKLOAD, "scout", frozenset({"MISSION_WORKER"}))
        created = self.service.create_mission(actor=self.owner, body={
            "organization_id": ORG, "workspace_id": WORKSPACE,
            "title": "Federated corpus audit", "objective": "Read governed evidence.",
        })
        self.mission_id = created.body["id"]
        self.binding = ScopeBinding(BINDING_ID, "1.0.0")

    def _grant(self, operations=frozenset({"READ_KNOWLEDGE"})):
        return self.service.issue_delegation(
            issuer=self.owner, subject=self.worker, mission_id=self.mission_id,
            allowed_operations=operations, roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )

    @staticmethod
    def _client(called):
        def transport(token, request):
            called.append({"token": token(), "request": request})
            arguments = request["arguments"]
            return McpResponse(200, {
                "schema_version": "1.0", "request_id": arguments["request_id"],
                "correlation_id": arguments["correlation_id"], "binding": arguments["binding"],
                "tabula_audit_correlation_id": TABULA_AUDIT_ID,
                "results": [{
                    "record_id": "adr-001", "domain": "architecture", "revision": "r1",
                    "canonical_uri": "urn:pantheon:tabula:corpus:adr-001",
                    "source": {"citation": "Sensitive citation", "uri": "https://example.test/adr-001"},
                    "recorded_at": "2026-09-15T00:00:00Z", "retrieved_at": "2026-09-15T00:00:01Z",
                    "selection_explanation": "Matches query.", "content": "Sensitive corpus content",
                }],
            })
        return TabulaCorpusClient(transport)

    def test_authorizes_and_audits_references_without_content_query_or_token(self):
        called = []
        result = self.service.retrieve_federated_corpus(
            mission_id=self.mission_id, worker=self.worker, delegation_id=self._grant(),
            client=self._client(called), token=lambda: "delegated-token",
            binding=self.binding, query="sensitive query", correlation_id=CORRELATION_ID,
        )
        self.assertEqual(result.records[0].content, "Sensitive corpus content")
        self.assertEqual(called[0]["token"], "delegated-token")
        events = [event for event in self.service.kernel.audit_events(self.mission_id) if event.event_type.startswith("EXTERNAL_READ")]
        self.assertEqual([event.event_type for event in events], ["EXTERNAL_READ_AUTHORIZATION_EVALUATED", "EXTERNAL_READ_COMPLETED"])
        payload = json.dumps(events[-1].data, sort_keys=True)
        self.assertIn(TABULA_AUDIT_ID, payload)
        self.assertIn("adr-001", payload)
        self.assertNotIn("Sensitive corpus content", payload)
        self.assertNotIn("Sensitive citation", payload)
        self.assertNotIn("sensitive query", payload)
        self.assertNotIn("delegated-token", payload)

    def test_invalid_request_records_a_redacted_terminal_rejection(self):
        called = []
        with self.assertRaisesRegex(ValueError, "TABULA_CORPUS_REQUEST_INVALID"):
            self.service.retrieve_federated_corpus(
                mission_id=self.mission_id, worker=self.worker, delegation_id=self._grant(),
                client=self._client(called), token=lambda: "delegated-token",
                binding=self.binding, query="", correlation_id=CORRELATION_ID,
            )
        self.assertEqual(called, [])
        events = [event for event in self.service.kernel.audit_events(self.mission_id) if event.event_type.startswith("EXTERNAL_READ")]
        self.assertEqual(events[-1].event_type, "EXTERNAL_READ_REJECTED")
        self.assertEqual(events[-1].data["error_code"], "INVALID_REQUEST")


    def test_denial_never_calls_tabula_and_records_rejected_read(self):
        called = []
        with self.assertRaisesRegex(AuthorizationError, "DELEGATED_OPERATION_DENIED"):
            self.service.retrieve_federated_corpus(
                mission_id=self.mission_id, worker=self.worker, delegation_id=self._grant(frozenset({"READ_MISSION"})),
                client=self._client(called), token=lambda: "delegated-token",
                binding=self.binding, query="sensitive query", correlation_id=CORRELATION_ID,
            )
        self.assertEqual(called, [])
        events = [event for event in self.service.kernel.audit_events(self.mission_id) if event.event_type.startswith("EXTERNAL_READ")]
        self.assertEqual(events[-1].event_type, "EXTERNAL_READ_REJECTED")
        self.assertEqual(events[-1].data["error_code"], "DELEGATED_OPERATION_DENIED")


if __name__ == "__main__":
    unittest.main()
