import tempfile
import unittest
from pathlib import Path

from aquila_api import DelegationGrant, PersistentAquilaService
from legion_kernel import AuthorizationError, Principal, PrincipalType, RoeLevel, WorkerKilled
from legion_runtime import ExecutionState


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
        self.assertEqual(len(restarted.get_timeline(actor=self.owner, mission_id=mission_id).body['events']), 4)
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
        self.assertEqual(len(authorization_events), 2)
        self.assertTrue(all(event.result == 'ALLOW' for event in authorization_events))
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


if __name__ == '__main__':
    unittest.main()
