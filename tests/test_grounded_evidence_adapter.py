import unittest

from legion_kernel import Principal, PrincipalType
from legion_runtime import (
    AuthorityDenied,
    EvidenceReadError,
    GroundedEvidenceReadRequest,
)
from legion_tabula import McpResponse, ScopeBinding, TabulaCorpusClient
from legion_tabula.runtime_adapter import (
    AuthorizedKnowledgeCredential,
    FederatedCorpusEvidenceReader,
)


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
MISSION = "33333333-3333-4333-8333-333333333333"
AGENT = "44444444-4444-4444-8444-444444444444"
ASSIGNMENT = "55555555-5555-4555-8555-555555555555"
WORK = "66666666-6666-4666-8666-666666666666"
ATTEMPT = "77777777-7777-4777-8777-777777777777"
CORRELATION = "88888888-8888-4888-8888-888888888888"
BINDING = "99999999-9999-4999-8999-999999999999"
AUDIT = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class RecordingAuthority:
    def __init__(self):
        self.credentials = []
        self.outcomes = []
        self.error = None

    def authorize_operation(self, request, binding):
        if self.error:
            raise self.error
        number = len(self.credentials) + 1
        credential = AuthorizedKnowledgeCredential(
            decision_id=f"decision-{number}",
            policy_version="policy-1",
            invocation_id=f"invocation-{number}",
            token=f"secret-token-{number}",
        )
        self.credentials.append(credential)
        return credential

    def record_outcome(self, request, binding, **kwargs):
        self.outcomes.append(kwargs)


class GroundedEvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.binding = ScopeBinding(BINDING, "1.0.0")
        self.authority = RecordingAuthority()
        self.request = GroundedEvidenceReadRequest(
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_id=MISSION,
            agent_id=AGENT,
            assignment_id=ASSIGNMENT,
            workload=Principal(PrincipalType.WORKLOAD, "scout-workload"),
            delegation_id="delegation-one",
            work_item_id=WORK,
            attempt_id=ATTEMPT,
            query="bounded evidence",
            correlation_id=CORRELATION,
        )

    @staticmethod
    def _success(arguments, *, content="bounded content"):
        return McpResponse(
            200,
            {
                "schema_version": "1.0",
                "request_id": arguments["request_id"],
                "correlation_id": arguments["correlation_id"],
                "binding": arguments["binding"],
                "tabula_audit_correlation_id": AUDIT,
                "results": [
                    {
                        "record_id": "record-one",
                        "domain": "architecture",
                        "revision": "rev-1",
                        "canonical_uri": "tabula://corpus/record-one/rev-1",
                        "source": {
                            "citation": "Hidden citation text",
                            "uri": "https://example.test/record-one",
                        },
                        "recorded_at": "2026-09-18T00:00:00Z",
                        "retrieved_at": "2026-09-18T00:01:00Z",
                        "selection_explanation": "Matches the bounded query.",
                        "content": content,
                    }
                ],
            },
        )

    def test_every_protected_operation_gets_fresh_credential_and_retry_is_correlated(self):
        calls = []

        def transport(token, request):
            arguments = request["arguments"]
            if not calls:
                tokens = (token(), token(), token())
                calls.append((arguments, tokens))
                return McpResponse(
                    200,
                    {
                        "schema_version": "1.0",
                        "request_id": arguments["request_id"],
                        "correlation_id": arguments["correlation_id"],
                        "code": "SERVICE_UNAVAILABLE",
                        "retryable": True,
                        "retry_after_ms": 1,
                        "tabula_audit_correlation_id": AUDIT,
                    },
                )
            tokens = (token(),)
            calls.append((arguments, tokens))
            return self._success(arguments)

        reader = FederatedCorpusEvidenceReader(
            client=TabulaCorpusClient(transport),
            authority=self.authority,
            binding=self.binding,
        )
        bundle = reader.read(self.request)

        self.assertEqual(len(self.authority.credentials), 4)
        self.assertEqual(
            bundle.authorization_decision_ids,
            ("decision-1", "decision-2", "decision-3", "decision-4"),
        )
        self.assertEqual(bundle.successful_authorization_decision_id, "decision-4")
        self.assertNotEqual(calls[0][0]["request_id"], calls[1][0]["request_id"])
        self.assertEqual(
            [item[0]["correlation_id"] for item in calls],
            [CORRELATION, CORRELATION],
        )
        self.assertEqual(
            [token for _, tokens in calls for token in tokens],
            [
                "secret-token-1",
                "secret-token-2",
                "secret-token-3",
                "secret-token-4",
            ],
        )
        self.assertEqual(len(self.authority.outcomes), 1)
        outcome = self.authority.outcomes[0]
        self.assertEqual(outcome["result"], "SUCCESS")
        self.assertEqual(
            outcome["successful_authorization_decision_id"], "decision-4"
        )
        safe_text = repr(bundle) + repr(outcome)
        self.assertNotIn("secret-token", safe_text)
        self.assertNotIn("Hidden citation text", safe_text)

    def test_over_limit_content_fails_without_returning_partial_evidence(self):
        def transport(token, request):
            token()
            return self._success(request["arguments"], content="é" * 5000)

        reader = FederatedCorpusEvidenceReader(
            client=TabulaCorpusClient(transport),
            authority=self.authority,
            binding=self.binding,
        )
        with self.assertRaisesRegex(EvidenceReadError, "EVIDENCE_BOUNDS_EXCEEDED"):
            reader.read(self.request)
        self.assertEqual(len(self.authority.outcomes), 1)
        self.assertEqual(self.authority.outcomes[0]["result"], "REJECTED")
        self.assertEqual(
            self.authority.outcomes[0]["error_code"], "EVIDENCE_BOUNDS_EXCEEDED"
        )
        self.assertNotIn("é", repr(self.authority.outcomes))

    def test_denial_stops_transport_before_response_or_outcome(self):
        self.authority.error = AuthorityDenied("DELEGATION_REVOKED")
        protected_calls = []

        def transport(token, request):
            protected_calls.append("authorize")
            token()
            self.fail("transport must not proceed after denied token issuance")

        reader = FederatedCorpusEvidenceReader(
            client=TabulaCorpusClient(transport),
            authority=self.authority,
            binding=self.binding,
        )
        with self.assertRaisesRegex(AuthorityDenied, "DELEGATION_REVOKED"):
            reader.read(self.request)
        self.assertEqual(protected_calls, ["authorize"])
        self.assertEqual(self.authority.outcomes, [])

    def test_credential_representation_redacts_token(self):
        credential = AuthorizedKnowledgeCredential(
            decision_id="decision-one",
            policy_version="policy-one",
            invocation_id="invocation-one",
            token="never-print-this",
        )
        self.assertNotIn("never-print-this", repr(credential))
        self.assertIn("[REDACTED]", repr(credential))


if __name__ == "__main__":
    unittest.main()
