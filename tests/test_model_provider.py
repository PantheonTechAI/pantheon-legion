import unittest

from aquila_api import AquilaService, DelegationGrant
from legion_cognition import (
    LangGraphScoutRuntime,
    MissionContext,
    ModelInvocationError,
    ModelInvocationResponse,
    ModelProviderScoutResponder,
    ModelProviderTimeout,
    ScoutEvidence,
    ScoutInvocationPolicy,
    ScoutRequest,
)
from legion_kernel import Principal, PrincipalType, RoeLevel


class TimeoutThenResponseProvider:
    def __init__(self):
        self.calls = []

    def invoke(self, request):
        self.calls.append(request)
        if request.attempt == 1:
            raise ModelProviderTimeout()
        return ModelInvocationResponse(
            recommendation='Investigate the redacted evidence.',
            provider='test-provider', model='test-model', response_id='response-42',
        )


class AlwaysTimeoutProvider:
    def invoke(self, request):
        raise ModelProviderTimeout()


class ModelProviderScoutResponderTests(unittest.TestCase):
    def setUp(self):
        self.request = ScoutRequest(
            context=MissionContext(
                mission_id='mission-1', mission_version=3,
                title='token=title-secret', objective='Protect password: objective-secret.',
                status='ACTIVE', roe_level='OBSERVE', constraints=('Bearer constraint-secret',),
            ),
            scout=Principal(PrincipalType.WORKLOAD, 'scout', frozenset({'MISSION_WORKER'})),
            query='Investigate Bearer query-secret.',
            granted_capabilities=frozenset({'read.mission'}),
            evidence=(ScoutEvidence(
                source='https://example.invalid?api_key=source-secret',
                summary='authorization: evidence-secret', observed_at='2026-09-13T00:00:00Z',
            ),),
        )

    def test_redacts_provider_input_retries_only_timeout_and_returns_digest_provenance(self):
        provider = TimeoutThenResponseProvider()
        result = LangGraphScoutRuntime(
            ModelProviderScoutResponder(provider, policy=ScoutInvocationPolicy(timeout_seconds=4, max_attempts=2))
        ).run_scout(self.request)

        self.assertEqual([call.attempt for call in provider.calls], [1, 2])
        self.assertEqual(provider.calls[0].invocation_id, provider.calls[1].invocation_id)
        self.assertEqual(provider.calls[0].timeout_seconds, 4)
        provider_input = repr(provider.calls)
        for secret in ('title-secret', 'objective-secret', 'constraint-secret', 'query-secret', 'source-secret', 'evidence-secret'):
            self.assertNotIn(secret, provider_input)
        self.assertEqual(result.model_invocation.provider, 'test-provider')
        self.assertEqual(result.model_invocation.model, 'test-model')
        self.assertEqual(result.model_invocation.response_id, 'response-42')
        self.assertEqual(result.model_invocation.attempts, 2)
        self.assertEqual(len(result.model_invocation.request_digest), 64)
        self.assertEqual(len(result.model_invocation.response_digest), 64)

    def test_exhausted_timeouts_produce_auditable_failure_provenance(self):
        with self.assertRaises(ModelInvocationError) as raised:
            ModelProviderScoutResponder(
                AlwaysTimeoutProvider(), policy=ScoutInvocationPolicy(timeout_seconds=1, max_attempts=2)
            ).recommend(context=self.request.context, query=self.request.query, evidence=self.request.evidence)

        self.assertEqual(raised.exception.error_code, 'MODEL_TIMEOUT')
        self.assertEqual(raised.exception.provenance.attempts, 2)
        self.assertEqual(raised.exception.provenance.error_code, 'MODEL_TIMEOUT')
        self.assertIsNone(raised.exception.provenance.response_digest)

    def test_aquila_records_only_model_provenance_for_success_and_failure(self):
        owner = Principal(PrincipalType.HUMAN, 'owner', frozenset({'MISSION_OWNER', 'OPERATOR'}))
        scout = Principal(PrincipalType.WORKLOAD, 'scout', frozenset({'MISSION_WORKER'}))
        service = AquilaService()
        created = service.create_mission(actor=owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Provider audit mission', 'objective': 'Audit model provenance.',
        })
        mission_id = created.body['id']
        delegation = DelegationGrant(
            grant_id='scout-grant', issuer=owner, subject=scout, mission_id=mission_id,
            allowed_operations=frozenset({'READ_MISSION'}), roe_ceiling=RoeLevel.OBSERVE,
            expires_at='9999-01-01T00:00:00Z',
        )
        runtime = LangGraphScoutRuntime(ModelProviderScoutResponder(TimeoutThenResponseProvider()))
        result = service.run_scout(
            mission_id=mission_id, scout=scout, delegation=delegation, runtime=runtime,
            query='Bearer audit-query-secret', granted_capabilities=frozenset({'read.mission'}),
            evidence=(ScoutEvidence(
                source='metrics://api', summary='token=audit-evidence-secret',
                observed_at='2026-09-13T00:00:00Z',
            ),),
        )
        events = service.kernel.timeline(mission_id)
        success = events[-1]
        self.assertEqual(success.event_type, 'MODEL_INVOCATION_COMPLETED')
        self.assertEqual(success.result, 'SUCCESS')
        self.assertEqual(success.data['invocation_id'], result.model_invocation.invocation_id)
        self.assertEqual(success.data['provider'], 'test-provider')
        self.assertEqual(success.data['attempts'], 2)
        self.assertNotIn('audit-query-secret', repr(success))
        self.assertNotIn('audit-evidence-secret', repr(success))

        with self.assertRaisesRegex(ModelInvocationError, 'MODEL_TIMEOUT'):
            service.run_scout(
                mission_id=mission_id, scout=scout, delegation=delegation,
                runtime=LangGraphScoutRuntime(ModelProviderScoutResponder(AlwaysTimeoutProvider())),
                query='Timeout safely.', granted_capabilities=frozenset({'read.mission'}),
            )
        failure = service.kernel.timeline(mission_id)[-1]
        self.assertEqual((failure.event_type, failure.result, failure.data['error_code']),
                         ('MODEL_INVOCATION_FAILED', 'FAILED', 'MODEL_TIMEOUT'))


if __name__ == '__main__':
    unittest.main()
