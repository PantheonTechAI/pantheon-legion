import unittest
from uuid import uuid4

from legion_tabula import CorpusReadError, McpResponse, ScopeBinding, TabulaCorpusClient


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
BINDING_ID = "33333333-3333-4333-8333-333333333333"
CORRELATION_ID = "44444444-4444-4444-8444-444444444444"
TABULA_AUDIT_ID = "55555555-5555-4555-8555-555555555555"


class TabulaCorpusClientTests(unittest.TestCase):
    def setUp(self):
        self.binding = ScopeBinding(BINDING_ID, "1.0.0")
        self.calls = []

    def _transport(self, responder):
        calls = self.calls

        def transport(token, request):
            calls.append({"token": token(), "request": request})
            return responder(request["arguments"])

        return transport

    @staticmethod
    def _success(arguments):
        return McpResponse(200, {
            "schema_version": "1.0",
            "request_id": arguments["request_id"],
            "correlation_id": arguments["correlation_id"],
            "binding": arguments["binding"],
            "tabula_audit_correlation_id": TABULA_AUDIT_ID,
            "results": [{
                "record_id": "adr-001",
                "domain": "architecture",
                "revision": "r7",
                "canonical_uri": "urn:pantheon:tabula:corpus:adr-001",
                "source": {"citation": "Architecture decision record", "uri": "https://example.test/adr-001"},
                "recorded_at": "2026-09-15T00:00:00Z",
                "retrieved_at": "2026-09-15T00:01:00Z",
                "selection_explanation": "Matches the bounded authorization query.",
                "content": "Raw corpus content is available to the caller but not Mission audit.",
            }],
        })

    def test_validates_scoped_success_and_exposes_only_safe_audit_references(self):
        client = TabulaCorpusClient(self._transport(self._success))
        result = client.read(
            token=lambda: "fresh-token", binding=self.binding, query="bounded authorization",
            correlation_id=CORRELATION_ID,
        )
        self.assertEqual(result.correlation_id, CORRELATION_ID)
        self.assertEqual(result.records[0].content, "Raw corpus content is available to the caller but not Mission audit.")
        self.assertEqual(result.audit_data(), {
            "tabula_audit_correlation_id": TABULA_AUDIT_ID,
            "record_references": [{
                "record_id": "adr-001", "revision": "r7",
                "canonical_uri": "urn:pantheon:tabula:corpus:adr-001",
            }],
        })
        sent = self.calls[0]["request"]
        self.assertEqual(sent["name"], "legion_search_corpus")
        self.assertEqual(self.calls[0]["token"], "fresh-token")
        self.assertNotIn("organization_id", sent["arguments"])
        self.assertNotIn("workspace_id", sent["arguments"])

    def test_retries_once_with_new_request_id_and_stable_correlation(self):
        attempts = []

        def responder(arguments):
            attempts.append(arguments)
            if len(attempts) == 1:
                return McpResponse(200, {
                    "schema_version": "1.0",
                    "request_id": arguments["request_id"],
                    "correlation_id": arguments["correlation_id"],
                    "code": "SERVICE_UNAVAILABLE",
                    "retryable": True,
                    "retry_after_ms": 25,
                    "tabula_audit_correlation_id": TABULA_AUDIT_ID,
                })
            return self._success(arguments)

        client = TabulaCorpusClient(self._transport(responder))
        result = client.read(
            token=lambda: f"fresh-{len(self.calls)}", binding=self.binding,
            query="bounded authorization", correlation_id=CORRELATION_ID,
        )
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(attempts[0]["request_id"], attempts[1]["request_id"])
        self.assertEqual([item["correlation_id"] for item in attempts], [CORRELATION_ID, CORRELATION_ID])
        self.assertEqual(result.correlation_id, CORRELATION_ID)
        self.assertEqual([call["token"] for call in self.calls], ["fresh-0", "fresh-1"])

    def test_rejects_malformed_success_without_leaking_payload(self):
        def malformed(arguments):
            response = self._success(arguments).body
            response["results"][0]["unexpected"] = "must not accept extras"
            return McpResponse(200, response)

        client = TabulaCorpusClient(self._transport(malformed))
        with self.assertRaisesRegex(CorpusReadError, "TABULA_PROTOCOL_ERROR") as raised:
            client.read(token=lambda: "fresh-token", binding=self.binding, query="bounded authorization")
        self.assertEqual(raised.exception.audit_data(), {"error_code": "TABULA_PROTOCOL_ERROR"})

    def test_preserves_generic_pre_tool_authentication_denial_without_audit_reference(self):
        client = TabulaCorpusClient(self._transport(lambda arguments: McpResponse(401, {"code": "UNAUTHENTICATED"})))
        with self.assertRaisesRegex(CorpusReadError, "UNAUTHENTICATED") as raised:
            client.read(token=lambda: "invalid-token", binding=self.binding, query="bounded authorization")
        self.assertEqual(raised.exception.audit_data(), {"error_code": "UNAUTHENTICATED"})

    def test_rejects_invalid_inputs_before_transport(self):
        client = TabulaCorpusClient(self._transport(self._success))
        with self.assertRaisesRegex(ValueError, "TABULA_CORPUS_REQUEST_INVALID"):
            client.read(token=lambda: "fresh-token", binding=self.binding, query="", limit=10)
        with self.assertRaisesRegex(ValueError, "TABULA_BINDING_INVALID"):
            ScopeBinding(str(uuid4()), "not-a-version")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
