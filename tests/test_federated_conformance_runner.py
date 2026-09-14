import unittest
from uuid import uuid4

from tests.federation.runner import FederatedConformanceRunner, McpReply


class FederatedConformanceRunnerTests(unittest.TestCase):
    def setUp(self):
        self.arguments = {
            "organization_id": str(uuid4()), "workspace_id": str(uuid4()),
            "binding": {"id": str(uuid4()), "version": "1.0.0"},
            "request_id": str(uuid4()), "correlation_id": str(uuid4()),
            "schema_version": "1.0", "intent": "SCOUT_EVIDENCE", "query": "least privilege", "limit": 1,
        }
        self.tokens = []

    def _issue(self, claims):
        self.tokens.append(claims)
        return f"token-{len(self.tokens)}"

    def test_success_strips_fixture_tenant_fields_from_mcp_arguments(self):
        seen = {}
        def call(token, request):
            seen.update(token=token(), request=request)
            args = request["arguments"]
            return McpReply(200, {"schema_version": "1.0", "request_id": args["request_id"], "correlation_id": args["correlation_id"], "tabula_audit_correlation_id": str(uuid4()), "results": []})
        result = FederatedConformanceRunner(self._issue, call).success("C1", "TABULA_CORPUS_READ", "legion_search_corpus", self.arguments)
        self.assertTrue(result.passed)
        self.assertNotIn("organization_id", seen["request"]["arguments"])
        self.assertEqual(self.tokens[0]["organization_id"], self.arguments["organization_id"])

    def test_pre_tool_and_post_auth_denials_are_distinguished(self):
        runner = FederatedConformanceRunner(self._issue, lambda token, request: (token(), McpReply)[1](401, {"code": "UNAUTHENTICATED"}))
        self.assertTrue(runner.pre_tool_denial("C2", "bad", "legion_search_corpus", self.arguments).passed)
        runner = FederatedConformanceRunner(self._issue, lambda token, request: (token(), McpReply)[1](200, {"code": "AUTHORIZATION_DENIED", "retryable": False, "tabula_audit_correlation_id": str(uuid4())}))
        self.assertTrue(runner.post_auth_denial("C3", "TABULA_CORPUS_READ", "legion_search_corpus", self.arguments).passed)

    def test_retry_requires_new_request_id_and_stable_correlation(self):
        retried = dict(self.arguments, request_id=str(uuid4()))
        replies = iter((McpReply(200, {"code": "SERVICE_UNAVAILABLE", "retryable": True}), McpReply(200, {"schema_version": "1.0"})))
        result = FederatedConformanceRunner(self._issue, lambda token, request: (token(), next(replies))[1]).retry("C4", "TABULA_CORPUS_READ", "legion_search_corpus", self.arguments, retried)
        self.assertTrue(result.passed)
        self.assertEqual(len(self.tokens), 2)


if __name__ == "__main__":
    unittest.main()
