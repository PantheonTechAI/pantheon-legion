import tempfile
import unittest
from pathlib import Path

from aquila_api import DelegationGrant, PersistentAquilaService
from legion_cognition import (
    LangGraphScoutRuntime,
    ModelInvocationResponse,
    ModelProviderScoutResponder,
)
from legion_fabrica import InMemoryFabrica, ToolDefinition
from legion_kernel import AuthorizationError, Principal, PrincipalType, RoeLevel, WorkerKilled
from legion_runtime import ExecutionState


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

    def execution_grant(self, mission_id):
        return DelegationGrant(
            grant_id='worker-execution-grant',
            issuer=self.owner,
            subject=self.worker,
            mission_id=mission_id,
            allowed_operations=frozenset({'EXECUTE_ACTION'}),
            roe_ceiling=RoeLevel.REVIEW,
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
        service.close()

        restarted = self.create_service()
        self.assertEqual(restarted.get_mission(actor=self.owner, mission_id=mission_id).body['version'], 3)
        self.assertEqual(len(restarted.get_timeline(actor=self.owner, mission_id=mission_id).body['events']), 7)
        with self.assertRaises(WorkerKilled):
            restarted.execute_action(
                mission_id=mission_id,
                action_id='33333333-3333-4333-8333-333333333333',
                worker=self.worker,
                delegation=self.execution_grant(mission_id),
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
            delegation=self.execution_grant(mission_id),
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
        with self.assertRaises(WorkerKilled):
            service.execute_action(
                mission_id=mission_id,
                action_id='44444444-4444-4444-8444-444444444444',
                worker=self.worker,
                delegation=self.execution_grant(mission_id),
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
                delegation=self.execution_grant(mission_id),
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
            delegation=DelegationGrant(
                grant_id='read-tool-grant', issuer=self.owner, subject=self.worker,
                mission_id=mission_id, allowed_operations=frozenset({'READ_TOOL'}),
                roe_ceiling=RoeLevel.OBSERVE, expires_at='9999-01-01T00:00:00Z',
            ),
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
            delegation=DelegationGrant(
                grant_id='persistent-scout-grant', issuer=self.owner, subject=self.worker,
                mission_id=mission_id, allowed_operations=frozenset({'READ_MISSION'}),
                roe_ceiling=RoeLevel.OBSERVE, expires_at='9999-01-01T00:00:00Z',
            ),
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
