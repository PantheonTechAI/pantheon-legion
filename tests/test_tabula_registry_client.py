import unittest
from legion_tabula import McpResponse, ScopeBinding, TabulaRegistryClient
from legion_tabula.mcp import McpTransportError

BINDING = ScopeBinding("33333333-3333-4333-8333-333333333333", "1.0.0")
CORRELATION = "44444444-4444-4444-8444-444444444444"
AUDIT = "55555555-5555-4555-8555-555555555555"

class RegistryClientTests(unittest.TestCase):
    def test_validates_discovery_metadata_and_strips_authority(self):
        calls = []
        def transport(token, request):
            calls.append((token(), request)); args = request["arguments"]
            return McpResponse(200, {"schema_version":"1.0", "request_id":args["request_id"], "correlation_id":args["correlation_id"], "binding":args["binding"], "tabula_audit_correlation_id":AUDIT, "results":[{"entity_id":"tool-1", "kind":"tool", "version":"1.2", "lifecycle_state":"ACTIVE", "validation_result":"VALID", "artifact_hash":"a" * 64}]})
        result = TabulaRegistryClient(transport).discover(token=lambda: "fresh", binding=BINDING, query="tool", correlation_id=CORRELATION)
        self.assertEqual(calls[0][1]["name"], "legion_discover_registry")
        self.assertNotIn("organization_id", calls[0][1]["arguments"])
        self.assertEqual(result.audit_data()["registry_references"], [{"entity_id":"tool-1", "version":"1.2", "lifecycle_state":"ACTIVE", "validation_result":"VALID", "artifact_hash":"a" * 64, "artifact_uri":None}])

    def test_rejects_invalid_entity(self):
        def transport(token, request):
            args=request["arguments"]
            return McpResponse(200, {"schema_version":"1.0", "request_id":args["request_id"], "correlation_id":args["correlation_id"], "binding":args["binding"], "tabula_audit_correlation_id":AUDIT, "results":[{"entity_id":"tool-1", "kind":"Tool", "version":"1.2", "lifecycle_state":"ACTIVE", "validation_result":"VALID", "artifact_uri":"https://example.test/x"}]})
        with self.assertRaisesRegex(Exception, "TABULA_PROTOCOL_ERROR"):
            TabulaRegistryClient(transport).discover(token=lambda: "fresh", binding=BINDING, query="tool")

    def test_retries_only_service_unavailable_with_fresh_request_identity(self):
        attempts = []

        def transport(token, request):
            arguments = request["arguments"]
            attempts.append(arguments)
            if len(attempts) == 1:
                return McpResponse(200, {
                    "schema_version": "1.0", "request_id": arguments["request_id"],
                    "correlation_id": arguments["correlation_id"], "code": "SERVICE_UNAVAILABLE",
                    "retryable": True, "retry_after_ms": 1,
                    "tabula_audit_correlation_id": AUDIT,
                })
            return McpResponse(200, {
                "schema_version": "1.0", "request_id": arguments["request_id"],
                "correlation_id": arguments["correlation_id"], "binding": arguments["binding"],
                "tabula_audit_correlation_id": AUDIT, "results": [],
            })

        result = TabulaRegistryClient(transport).discover(
            token=lambda: "fresh", binding=BINDING, query="tool", correlation_id=CORRELATION,
        )
        self.assertEqual(result.correlation_id, CORRELATION)
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(attempts[0]["request_id"], attempts[1]["request_id"])
        self.assertEqual([attempt["correlation_id"] for attempt in attempts], [CORRELATION, CORRELATION])

    def test_deadline_and_malformed_responses_fail_closed_without_retry(self):
        calls = []

        def deadline(token, request):
            arguments = request["arguments"]
            calls.append(arguments)
            return McpResponse(200, {
                "schema_version": "1.0", "request_id": arguments["request_id"],
                "correlation_id": arguments["correlation_id"], "code": "DEADLINE_EXCEEDED",
                "retryable": False, "tabula_audit_correlation_id": AUDIT,
            })

        with self.assertRaisesRegex(Exception, "DEADLINE_EXCEEDED"):
            TabulaRegistryClient(deadline).discover(token=lambda: "fresh", binding=BINDING, query="tool")
        self.assertEqual(len(calls), 1)

        def malformed(token, request):
            arguments = request["arguments"]
            return McpResponse(200, {
                "schema_version": "1.0", "request_id": arguments["request_id"],
                "correlation_id": arguments["correlation_id"], "binding": arguments["binding"],
                "tabula_audit_correlation_id": AUDIT, "results": [{"entity_id": "tool-1"}],
            })

        with self.assertRaisesRegex(Exception, "TABULA_PROTOCOL_ERROR"):
            TabulaRegistryClient(malformed).discover(token=lambda: "fresh", binding=BINDING, query="tool")

    def test_local_transport_deadline_is_not_misclassified_as_service_unavailable(self):
        def deadline(token, request):
            raise McpTransportError("DEADLINE_EXCEEDED")

        with self.assertRaisesRegex(Exception, "DEADLINE_EXCEEDED"):
            TabulaRegistryClient(deadline).discover(token=lambda: "fresh", binding=BINDING, query="tool")

if __name__ == "__main__": unittest.main()
