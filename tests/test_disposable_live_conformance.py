import unittest
from uuid import uuid4

from tests.federation.live import DisposableRun, run_disposable_conformance
from tests.federation.runner import McpReply
from tests.federation import live


class DisposableLiveConformanceTests(unittest.TestCase):
    def test_runs_matrix_after_start_callback_receives_docker_sts_url(self):
        received = []

        def start_stack(sts_url):
            received.append(sts_url)

        class Transport:
            def __init__(self, endpoint):
                self.endpoint = endpoint

            def __call__(self, token, request):
                args = request["arguments"]
                if token == "not-a-delegated-token":
                    return McpReply(401, {"code": "UNAUTHENTICATED"})
                if args["binding"]["id"] == live._SUSPENDED_BINDING_ID:
                    return McpReply(200, {"code": "AUTHORIZATION_DENIED", "retryable": False, "tabula_audit_correlation_id": str(uuid4())})
                return McpReply(200, {"schema_version": "1.0", "request_id": args["request_id"], "correlation_id": args["correlation_id"], "tabula_audit_correlation_id": str(uuid4()), "results": []})

        results = run_disposable_conformance(
            DisposableRun("http://127.0.0.1:18100/mcp", start_stack, Transport)
        )

        self.assertEqual([result.scenario_id for result in results], ["corpus-success", "registry-success", "invalid-token", "suspended-binding"])
        self.assertTrue(all(result.passed for result in results))
        self.assertEqual(len(received), 1)
        self.assertTrue(received[0].startswith("http://host.docker.internal:"))


if __name__ == "__main__":
    unittest.main()
