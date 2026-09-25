import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aquila_api import PersistentAquilaService
from legion_cognition import (
    LangGraphScoutRuntime,
    ModelInvocationResponse,
    ModelProviderScoutResponder,
)
from legion_fabrica import InMemoryFabrica, ToolDefinition
from legion_kernel import AuthorizationError, Principal, PrincipalType, RoeLevel, WorkerKilled
from legion_runtime import ExecutionState
from legion_store import StoreConflict
from legion_tabula import McpResponse, ScopeBinding, TabulaCorpusClient, TabulaRegistryClient


class PersistentTestModelProvider:
    def invoke(self, request):
        return ModelInvocationResponse(
            recommendation='Keep the recommendation read-only.',
            provider='persistent-test-provider', model='persistent-test-model',
            response_id='persistent-response',
        )


class PersistentAquilaServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temp_dir.name) / 'aquila.sqlite3')
        self.owner = Principal(PrincipalType.HUMAN, 'owner', frozenset({'MISSION_OWNER', 'OPERATOR'}))
        self.approver = Principal(PrincipalType.HUMAN, 'approver', frozenset({'APPROVER'}))
        self.worker = Principal(PrincipalType.WORKLOAD, 'worker', frozenset({'MISSION_WORKER'}))

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_service(self):
        return PersistentAquilaService(self.database)

    def grant(self, service, mission_id, operations, roe_ceiling=RoeLevel.REVIEW):
        return service.issue_delegation(
            issuer=self.owner, subject=self.worker, mission_id=mission_id,
            allowed_operations=frozenset(operations), roe_ceiling=roe_ceiling,
            expires_at='9999-01-01T00:00:00Z',
        )

    def test_mission_approval_and_audit_survive_service_restart(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Persistent API Mission',
            'objective': 'Survive process restart.',
            'initial_roe_level': 'REVIEW',
        })
        mission_id = created.body['id']
        service.submit_command(actor=self.owner, mission_id=mission_id, body={
            'expected_version': 1, 'idempotency_key': 'start', 'command_type': 'START', 'payload': {}
        })
        requested = service.submit_command(actor=self.owner, mission_id=mission_id, body={
            'expected_version': 2, 'idempotency_key': 'action', 'command_type': 'REQUEST_ACTION', 'payload': {
                'action_id': '33333333-3333-4333-8333-333333333333',
                'capability': 'test.mutation', 'arguments': {}, 'target': 'resource',
                'side_effect_class': 'MUTATION',
            }
        })
        approval = service.decide_approval(actor=self.approver, mission_id=mission_id, body={
            'approval_id': requested.body['approval_id'], 'expected_mission_version': 3,
            'decision': 'APPROVE', 'reason': 'Reviewed.',
        })
        self.assertEqual(approval.body['status'], 'APPROVED')
        grant_id = self.grant(service, mission_id, {'EXECUTE_ACTION'})
        service.close()

        restarted = self.create_service()
        self.assertEqual(restarted.get_mission(actor=self.owner, mission_id=mission_id).body['version'], 3)
        self.assertEqual(len(restarted.get_timeline(actor=self.owner, mission_id=mission_id).body['events']), 8)
        with self.assertRaises(WorkerKilled):
            restarted.execute_action(
                mission_id=mission_id,
                action_id='33333333-3333-4333-8333-333333333333',
                worker=self.worker,
                delegation_id=grant_id,
                fail_after_side_effect=True,
            )
        execution_id = restarted.action_executions['33333333-3333-4333-8333-333333333333']
        self.assertEqual(restarted.execution.query(execution_id).state, ExecutionState.FAILED)
        restarted.close()

        recovered = self.create_service()
        self.assertEqual(recovered.execute_action(
            mission_id=mission_id,
            action_id='33333333-3333-4333-8333-333333333333',
            worker=self.worker,
            delegation_id=grant_id,
        ), 'RECOVERED')
        self.assertEqual(recovered.kernel.side_effects['33333333-3333-4333-8333-333333333333'], 1)
        recovered_execution = recovered.execution.query(execution_id)
        self.assertEqual(recovered_execution.state, ExecutionState.COMPLETED)
        self.assertEqual(recovered_execution.attempt, 2)
        authorization_events = [
            event for event in recovered.kernel.timeline(mission_id)
            if event.event_type == 'AUTHORIZATION_EVALUATED'
        ]
        execution_authorizations = [
            event for event in authorization_events
            if event.data['operation'] == 'EXECUTE_ACTION'
        ]
        command_authorizations = [
            event for event in authorization_events
            if event.data['operation'] == 'SUBMIT_COMMAND'
        ]
        approval_authorizations = [
            event for event in authorization_events
            if event.data['operation'] == 'DECIDE_APPROVAL'
        ]
        self.assertEqual(len(execution_authorizations), 2)
        self.assertEqual(len(command_authorizations), 2)
        self.assertEqual(len(approval_authorizations), 1)
        self.assertTrue(all(event.result == 'ALLOW' for event in execution_authorizations))
        self.assertEqual(
            [(event.result, event.data['reason']) for event in approval_authorizations],
            [('ALLOW', 'AUTHORIZED')],
        )
        self.assertEqual(
            {(event.result, event.data['reason']) for event in command_authorizations},
            {('ALLOW', 'AUTHORIZED'), ('DENY', 'APPROVAL_REQUIRED')},
        )
        self.assertTrue(all(event.data['decision_id'] for event in authorization_events))
        recovered.close()

    def test_cancelled_execution_remains_cancelled_after_restart(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Cancelled execution', 'objective': 'Persist cancellation.',
            'initial_roe_level': 'REVIEW',
        })
        mission_id = created.body['id']
        service.submit_command(actor=self.owner, mission_id=mission_id, body={
            'expected_version': 1, 'idempotency_key': 'start', 'command_type': 'START', 'payload': {}
        })
        requested = service.submit_command(actor=self.owner, mission_id=mission_id, body={
            'expected_version': 2, 'idempotency_key': 'action', 'command_type': 'REQUEST_ACTION', 'payload': {
                'action_id': '44444444-4444-4444-8444-444444444444',
                'capability': 'test.mutation', 'arguments': {}, 'target': 'resource',
                'side_effect_class': 'MUTATION',
            }
        })
        service.decide_approval(actor=self.approver, mission_id=mission_id, body={
            'approval_id': requested.body['approval_id'], 'expected_mission_version': 3,
            'decision': 'APPROVE', 'reason': 'Reviewed.',
        })
        grant_id = self.grant(service, mission_id, {'EXECUTE_ACTION'})
        with self.assertRaises(WorkerKilled):
            service.execute_action(
                mission_id=mission_id,
                action_id='44444444-4444-4444-8444-444444444444',
                worker=self.worker,
                delegation_id=grant_id,
                fail_after_side_effect=True,
            )
        cancelled = service.cancel_mission(actor=self.owner, mission_id=mission_id, body={
            'expected_version': 4, 'idempotency_key': 'cancel', 'reason': 'Stop execution.',
        })
        self.assertEqual(cancelled.status_code, 200)
        execution_id = service.action_executions['44444444-4444-4444-8444-444444444444']
        self.assertEqual(service.execution.query(execution_id).state, ExecutionState.CANCELLED)
        service.close()

        restarted = self.create_service()
        self.assertEqual(restarted.execution.query(execution_id).state, ExecutionState.CANCELLED)
        with self.assertRaisesRegex(AuthorizationError, 'MISSION_TERMINAL'):
            restarted.execute_action(
                mission_id=mission_id,
                action_id='44444444-4444-4444-8444-444444444444',
                worker=self.worker,
                delegation_id=grant_id,
            )
        restarted.close()

    def test_idempotent_command_replays_after_restart(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Idempotency Mission', 'objective': 'Replay a command.'
        })
        mission_id = created.body['id']
        body = {'expected_version': 1, 'idempotency_key': 'start', 'command_type': 'START', 'payload': {}}
        first = service.submit_command(actor=self.owner, mission_id=mission_id, body=body)
        service.close()
        restarted = self.create_service()
        second = restarted.submit_command(actor=self.owner, mission_id=mission_id, body=body)
        self.assertEqual(second.status_code, first.status_code)
        self.assertEqual(second.body['command_id'], first.body['command_id'])
        conflict = restarted.submit_command(actor=self.owner, mission_id=mission_id, body={
            'expected_version': 1, 'idempotency_key': 'start', 'command_type': 'PAUSE', 'payload': {}
        })
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.body['code'], 'IDEMPOTENCY_KEY_REUSE')
        restarted.close()

    def test_command_snapshot_audit_and_idempotency_roll_back_together(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Atomic command persistence', 'objective': 'Reject partial commits.',
        })
        mission_id = created.body['id']
        body = {
            'expected_version': 1, 'idempotency_key': 'atomic-start',
            'command_type': 'START', 'payload': {},
        }
        with mock.patch.object(service.store, 'append_audit', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                service.submit_command(actor=self.owner, mission_id=mission_id, body=body)
        service.close()

        restarted = self.create_service()
        self.assertEqual(restarted.get_mission(actor=self.owner, mission_id=mission_id).body['version'], 1)
        self.assertEqual(len(restarted.get_timeline(actor=self.owner, mission_id=mission_id).body['events']), 1)
        self.assertIsNone(restarted.store.get_idempotency(
            mission_id=mission_id, idempotency_key='atomic-start',
        ))
        restarted.close()

    def test_delegation_audit_and_grant_roll_back_together(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Atomic delegation persistence', 'objective': 'Reject partial grants.',
        })
        mission_id = created.body['id']
        with mock.patch.object(service, '_persist_delegation', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.grant(service, mission_id, {'READ_MISSION'}, RoeLevel.OBSERVE)
        service.close()

        restarted = self.create_service()
        self.assertEqual(restarted.delegations, {})
        events = restarted.get_timeline(actor=self.owner, mission_id=mission_id).body['events']
        self.assertEqual([event['event_type'] for event in events], ['MISSION_CREATED'])
        restarted.close()

    def test_losing_concurrent_writer_persists_no_partial_authority_record(self):
        first = self.create_service()
        created = first.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Concurrent persistence', 'objective': 'Reject stale writers.',
        })
        mission_id = created.body['id']
        second = self.create_service()
        first.submit_command(actor=self.owner, mission_id=mission_id, body={
            'expected_version': 1, 'idempotency_key': 'winner', 'command_type': 'START', 'payload': {},
        })
        stale = second.submit_command(actor=self.owner, mission_id=mission_id, body={
            'expected_version': 1, 'idempotency_key': 'loser', 'command_type': 'START', 'payload': {},
        })
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.body['code'], 'VERSION_CONFLICT')
        self.assertEqual(second.get_mission(actor=self.owner, mission_id=mission_id).body['version'], 2)
        first.close()
        second.close()

        recovered = self.create_service()
        self.assertEqual(recovered.get_mission(actor=self.owner, mission_id=mission_id).body['version'], 2)
        self.assertEqual(recovered.store.get_idempotency(
            mission_id=mission_id, idempotency_key='loser',
        )['result']['body']['code'], 'VERSION_CONFLICT')
        events = recovered.get_timeline(actor=self.owner, mission_id=mission_id).body['events']
        self.assertEqual(sum(event['event_type'] == 'COMMAND_ACCEPTED' for event in events), 1)
        recovered.close()

    def test_participant_projection_survives_service_restart(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Participant Mission', 'objective': 'Persist participants.',
        })
        mission_id = created.body['id']
        added = service.submit_command(actor=self.owner, mission_id=mission_id, body={
            'expected_version': 1, 'idempotency_key': 'add-observer',
            'command_type': 'ADD_PARTICIPANT',
            'payload': {'participant': {
                'principal': {'type': 'HUMAN', 'subject': 'observer'},
                'role': 'OBSERVER', 'scope': 'read-only',
            }},
        })
        self.assertEqual(added.status_code, 200)
        service.close()

        restarted = self.create_service()
        mission = restarted.get_mission(actor=self.owner, mission_id=mission_id)
        self.assertEqual(mission.body['participants'], [{
            'principal': {'type': 'HUMAN', 'subject': 'observer'},
            'role': 'OBSERVER', 'scope': 'read-only',
        }])
        restarted.close()

    def test_fabrica_read_tool_audit_survives_service_restart(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Persistent tool audit', 'objective': 'Persist Fabrica audit facts.',
        })
        mission_id = created.body['id']
        fabrica = InMemoryFabrica()
        fabrica.register(ToolDefinition(
            capability='metrics.read', side_effect_class='READ',
            handler=lambda arguments: {'service': arguments['service']},
        ))
        service.invoke_read_tool(
            mission_id=mission_id,
            worker=self.worker,
            delegation_id=self.grant(service, mission_id, {'READ_TOOL'}, RoeLevel.OBSERVE),
            fabrica=fabrica,
            capability='metrics.read',
            arguments={'service': 'api'},
            correlation_id='persistent-tool-correlation',
        )
        service.close()

        restarted = self.create_service()
        events = restarted.get_timeline(actor=self.owner, mission_id=mission_id).body['events']
        tool_events = [event for event in events if event['event_type'].startswith('TOOL_')]
        self.assertEqual(
            [(event['event_type'], event['result']) for event in tool_events],
            [('TOOL_AUTHORIZATION_EVALUATED', 'ALLOW'), ('TOOL_EXECUTION_COMPLETED', 'SUCCESS')],
        )
        self.assertEqual(
            {event['correlation_id'] for event in tool_events}, {'persistent-tool-correlation'},
        )
        restarted.close()

    def test_federated_corpus_audit_survives_service_restart(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Persistent federated audit', 'objective': 'Persist Tabula read facts.',
        })
        mission_id = created.body['id']
        binding = ScopeBinding('33333333-3333-4333-8333-333333333333', '1.0.0')
        correlation_id = '44444444-4444-4444-8444-444444444444'

        def transport(token, request):
            arguments = request['arguments']
            self.assertEqual(token(), 'delegated-token')
            return McpResponse(200, {
                'schema_version': '1.0', 'request_id': arguments['request_id'],
                'correlation_id': arguments['correlation_id'], 'binding': arguments['binding'],
                'tabula_audit_correlation_id': '55555555-5555-4555-8555-555555555555',
                'results': [],
            })

        service.retrieve_federated_corpus(
            mission_id=mission_id, worker=self.worker,
            delegation_id=self.grant(service, mission_id, {'READ_KNOWLEDGE'}, RoeLevel.OBSERVE),
            client=TabulaCorpusClient(transport), token=lambda: 'delegated-token',
            binding=binding, query='durable audit', correlation_id=correlation_id,
        )
        service.close()

        restarted = self.create_service()
        events = [
            event for event in restarted.get_timeline(actor=self.owner, mission_id=mission_id).body['events']
            if event['event_type'].startswith('EXTERNAL_READ_')
        ]
        self.assertEqual(
            [(event['event_type'], event['result']) for event in events],
            [('EXTERNAL_READ_AUTHORIZATION_EVALUATED', 'ALLOW'), ('EXTERNAL_READ_COMPLETED', 'SUCCESS')],
        )
        self.assertEqual({event['correlation_id'] for event in events}, {correlation_id})
        self.assertEqual(
            events[-1]['data']['tabula_audit_correlation_id'],
            '55555555-5555-4555-8555-555555555555',
        )
        restarted.close()

    def test_federated_registry_audit_survives_service_restart(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Persistent Registry audit', 'objective': 'Persist Tabula discovery facts.',
        })
        mission_id = created.body['id']
        binding = ScopeBinding('33333333-3333-4333-8333-333333333333', '1.0.0')
        correlation_id = '44444444-4444-4444-8444-444444444444'

        def transport(token, request):
            arguments = request['arguments']
            self.assertEqual(token(), 'delegated-token')
            return McpResponse(200, {
                'schema_version': '1.0', 'request_id': arguments['request_id'],
                'correlation_id': arguments['correlation_id'], 'binding': arguments['binding'],
                'tabula_audit_correlation_id': '55555555-5555-4555-8555-555555555555',
                'results': [{
                    'entity_id': 'tool-1', 'kind': 'tool', 'version': '1.0',
                    'lifecycle_state': 'ACTIVE', 'validation_result': 'VALID',
                    'artifact_hash': 'a' * 64,
                }],
            })

        service.retrieve_federated_registry(
            mission_id=mission_id, worker=self.worker,
            delegation_id=self.grant(service, mission_id, {'READ_KNOWLEDGE'}, RoeLevel.OBSERVE),
            client=TabulaRegistryClient(transport), token=lambda: 'delegated-token',
            binding=binding, query='discover durable metadata', correlation_id=correlation_id,
        )
        service.close()

        restarted = self.create_service()
        events = [
            event for event in restarted.get_timeline(actor=self.owner, mission_id=mission_id).body['events']
            if event['event_type'].startswith('EXTERNAL_READ_')
        ]
        self.assertEqual(
            [(event['event_type'], event['result']) for event in events],
            [('EXTERNAL_READ_AUTHORIZATION_EVALUATED', 'ALLOW'), ('EXTERNAL_READ_COMPLETED', 'SUCCESS')],
        )
        self.assertEqual(events[-1]['data']['registry_references'], [{
            'entity_id': 'tool-1', 'version': '1.0', 'lifecycle_state': 'ACTIVE',
            'validation_result': 'VALID', 'artifact_hash': 'a' * 64, 'artifact_uri': None,
        }])
        restarted.close()

    def test_model_invocation_provenance_survives_service_restart(self):
        service = self.create_service()
        created = service.create_mission(actor=self.owner, body={
            'organization_id': '11111111-1111-4111-8111-111111111111',
            'workspace_id': '22222222-2222-4222-8222-222222222222',
            'title': 'Persistent model audit', 'objective': 'Persist model provenance.',
        })
        mission_id = created.body['id']
        service.run_scout(
            mission_id=mission_id,
            scout=self.worker,
            delegation_id=self.grant(service, mission_id, {'READ_MISSION'}, RoeLevel.OBSERVE),
            runtime=LangGraphScoutRuntime(ModelProviderScoutResponder(PersistentTestModelProvider())),
            query='Summarize the Mission.',
            granted_capabilities=frozenset({'read.mission'}),
        )
        service.close()

        restarted = self.create_service()
        event = [
            item for item in restarted.get_timeline(actor=self.owner, mission_id=mission_id).body['events']
            if item['event_type'] == 'MODEL_INVOCATION_COMPLETED'
        ][0]
        self.assertEqual(event['result'], 'SUCCESS')
        self.assertEqual(event['data']['provider'], 'persistent-test-provider')
        self.assertEqual(event['data']['model'], 'persistent-test-model')
        self.assertEqual(event['data']['response_id'], 'persistent-response')
        self.assertEqual(len(event['data']['request_digest']), 64)
        self.assertEqual(len(event['data']['response_digest']), 64)
        restarted.close()


if __name__ == '__main__':
    unittest.main()
