"""Behavioral proof for the first human investigation intent boundary."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aquila_api import PersistentAquilaService
from aquila_api.investigation import PROFILE
from legion_kernel import Principal, PrincipalType


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
SUBJECTS = ("runtime-centurion", "runtime-scout")


class InvestigationLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "aquila.sqlite3")
        self.owner = Principal(PrincipalType.HUMAN, "owner", frozenset({"MISSION_OWNER"}))
        self.operator = Principal(PrincipalType.HUMAN, "operator", frozenset({"OPERATOR"}))

    def tearDown(self):
        self.temp.cleanup()

    def service(self):
        return PersistentAquilaService(self.path, investigation_subjects=SUBJECTS)

    def active_mission(self, service):
        created = service.create_mission(actor=self.owner, body={
            "organization_id": ORG, "workspace_id": WORKSPACE,
            "title": "Investigate records", "objective": "Which ADRs govern delegated Scout evidence?",
        })
        mission_id = created.body["id"]
        started = service.submit_command(actor=self.owner, mission_id=mission_id, body={
            "expected_version": 1, "idempotency_key": "start", "command_type": "START", "payload": {},
        })
        self.assertEqual(started.status_code, 200)
        return mission_id

    def launch(self, service, mission_id, *, key="launch", actor=None):
        return service.submit_command(actor=actor or self.owner, mission_id=mission_id, body={
            "expected_version": 2, "idempotency_key": key,
            "command_type": "REQUEST_INVESTIGATION", "payload": {"profile": PROFILE},
        })

    def test_launch_replay_restart_and_delivery_ack_are_singular(self):
        service = self.service()
        mission_id = self.active_mission(service)
        launched = self.launch(service, mission_id)
        self.assertEqual(launched.status_code, 200)
        self.assertEqual(launched.body["delivery_status"], "PENDING")
        intent = service.outbox.get_by_mission(mission_id)
        self.assertEqual(intent.command_id, launched.body["command_id"])
        self.assertEqual(len(service.delegations), 2)
        self.assertEqual(set(service.outbox.pending()), {intent})
        self.assertEqual(self.launch(service, mission_id), launched)
        self.assertEqual(self.launch(service, mission_id, key="different").body["code"],
                         "INVESTIGATION_ALREADY_REQUESTED")
        service.close()

        restarted = self.service()
        self.assertEqual(self.launch(restarted, mission_id), launched)
        self.assertEqual(len(restarted.delegations), 2)
        with restarted.store.transaction():
            delivered = restarted.outbox.acknowledge(intent.command_id, "runtime-intake-1")
        self.assertEqual(delivered.status, "DELIVERED")
        with restarted.store.transaction():
            self.assertEqual(restarted.outbox.acknowledge(intent.command_id, "runtime-intake-1"), delivered)
        with self.assertRaisesRegex(ValueError, "DELIVERY_CONFLICT"):
            with restarted.store.transaction():
                restarted.outbox.acknowledge(intent.command_id, "another-intake")
        self.assertEqual(restarted.outbox.pending(), ())
        self.assertEqual(restarted.store.get_mission(mission_id).version, 3)
        restarted.close()

    def test_launch_rolls_back_grants_outbox_and_memory_after_failed_write(self):
        service = self.service()
        mission_id = self.active_mission(service)
        with mock.patch.object(service.outbox, "insert", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.launch(service, mission_id)
        self.assertEqual(service.kernel.get_mission(mission_id).version, 2)
        self.assertEqual(service.delegations, {})
        self.assertIsNone(service.outbox.get_by_mission(mission_id))
        self.assertIsNone(service.store.get_idempotency(mission_id=mission_id, idempotency_key="launch"))
        self.assertEqual(self.launch(service, mission_id).status_code, 200)
        self.assertEqual(len(service.delegations), 2)
        service.close()

    def test_worker_audit_does_not_stale_praetorium_command(self):
        ui = self.service()
        mission_id = self.active_mission(ui)
        launched = self.launch(ui, mission_id)
        intent = ui.outbox.get_by_mission(mission_id)
        worker_view = self.service()
        response = worker_view.authorize_agent_resume(
            workload=Principal(PrincipalType.WORKLOAD, SUBJECTS[0]),
            mission_id=mission_id,
            agent_id="33333333-3333-4333-8333-333333333333",
            assignment_id="44444444-4444-4444-8444-444444444444",
            binding_id="55555555-5555-4555-8555-555555555555",
            delegation_id=intent.centurion_grant_id,
            correlation_id=intent.command_id,
        )
        self.assertEqual(response.status_code, 200)
        worker_view.close()
        paused = ui.submit_command(actor=self.owner, mission_id=mission_id, body={
            "expected_version": 3, "idempotency_key": "pause-after-worker-audit",
            "command_type": "PAUSE", "payload": {},
        })
        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.body["mission_version"], 4)
        events = ui.store.get_audit(mission_id)
        self.assertEqual([event.sequence for event in events], list(range(1, len(events) + 1)))
        self.assertTrue(any(event.event_type == "AGENT_RUNTIME_AUTHORIZATION_EVALUATED"
                            for event in events))
        self.assertEqual(ui.outbox.get_by_mission(mission_id).command_id,
                         launched.body["command_id"])
        ui.close()

    def test_global_owner_role_cannot_launch_or_read_another_owners_investigation(self):
        service = self.service()
        mission_id = self.active_mission(service)
        other_owner = Principal(PrincipalType.HUMAN, "other-owner", frozenset({"MISSION_OWNER"}))
        self.assertEqual(self.launch(service, mission_id, actor=other_owner).body["code"],
                         "MISSION_OWNER_REQUIRED")
        self.assertEqual(service.get_investigation(actor=other_owner, mission_id=mission_id).status_code,
                         403)
        self.assertIsNone(service.outbox.get_by_mission(mission_id))
        self.assertEqual(self.launch(service, mission_id).status_code, 200)
        self.assertEqual(service.get_investigation(actor=other_owner, mission_id=mission_id).status_code,
                         403)
        service.close()

    def test_launch_requires_owner_active_mission_and_profile(self):
        service = self.service()
        mission_id = self.active_mission(service)
        self.assertEqual(self.launch(service, mission_id, actor=self.operator).body["code"],
                         "MISSION_OWNER_REQUIRED")
        invalid = service.submit_command(actor=self.owner, mission_id=mission_id, body={
            "expected_version": 2, "idempotency_key": "bad-profile",
            "command_type": "REQUEST_INVESTIGATION", "payload": {"profile": "ARBITRARY"},
        })
        self.assertEqual(invalid.body["code"], "INVALID_COMMAND_PAYLOAD")
        paused = service.submit_command(actor=self.owner, mission_id=mission_id, body={
            "expected_version": 2, "idempotency_key": "pause", "command_type": "PAUSE", "payload": {},
        })
        self.assertEqual(paused.status_code, 200)
        denied = service.submit_command(actor=self.owner, mission_id=mission_id, body={
            "expected_version": 3, "idempotency_key": "launch-paused",
            "command_type": "REQUEST_INVESTIGATION", "payload": {"profile": PROFILE},
        })
        self.assertEqual(denied.body["code"], "INVALID_STATE_TRANSITION")
        self.assertIsNone(service.outbox.get_by_mission(mission_id))
        self.assertEqual(service.delegations, {})
        service.close()


if __name__ == "__main__":
    unittest.main()
