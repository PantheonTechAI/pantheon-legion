import unittest
from legion_tabula import McpResponse, ScopeBinding, TabulaRegistryClient

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

if __name__ == "__main__": unittest.main()
