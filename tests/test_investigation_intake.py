"""Cross-store proof of one admitted investigation after local delivery retries."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aquila_api import PersistentAquilaService
from aquila_api.investigation import PROFILE
from aquila_api.investigation_dispatcher import InvestigationDispatchError, LocalInvestigationDispatcher
from legion_kernel import Principal, PrincipalType
from legion_runtime import PostgreSQLAgentStore, RuntimeInvestigationAdmissions, InvestigationAdmissionError
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
SUBJECTS = ("runtime-centurion", "runtime-scout")


class InvestigationIntakeTests(unittest.TestCase):
    def setUp(self):
        reset_runtime_database()
        self.temp = tempfile.TemporaryDirectory()
        self.aquila_path = str(Path(self.temp.name) / "aquila.sqlite3")
        self.owner = Principal(PrincipalType.HUMAN, "owner", frozenset({"MISSION_OWNER"}))
        self.aquila = PersistentAquilaService(self.aquila_path, investigation_subjects=SUBJECTS)
        created = self.aquila.create_mission(actor=self.owner, body={
            "organization_id": ORG, "workspace_id": WORKSPACE,
            "title": "Investigate ADRs", "objective": "Which ADRs govern Scout evidence?",
        })
        self.mission_id = created.body["id"]
        self.aquila.submit_command(actor=self.owner, mission_id=self.mission_id, body={
            "expected_version": 1, "idempotency_key": "start", "command_type": "START", "payload": {},
        })
        result = self.aquila.submit_command(actor=self.owner, mission_id=self.mission_id, body={
            "expected_version": 2, "idempotency_key": "launch",
            "command_type": "REQUEST_INVESTIGATION", "payload": {"profile": PROFILE},
        })
        self.command_id = result.body["command_id"]
        self.store = new_runtime_store()

    def tearDown(self):
        self.store.close()
        self.aquila.close()
        self.temp.cleanup()

    def dispatcher(self, store=None):
        return LocalInvestigationDispatcher(
            self.aquila_path, store or self.store, investigation_subjects=SUBJECTS,
        )

    def test_waiting_capacity_has_finite_deadline_and_terminal_reconciliation(self):
        intent = self.aquila.outbox.get_by_mission(self.mission_id)
        mission = self.aquila.store.get_mission(self.mission_id)
        intake = RuntimeInvestigationAdmissions(self.store).admit(intent, mission)
        deadline = datetime.fromisoformat(intake.deadline_at.replace("Z", "+00:00"))
        expiry = datetime.fromisoformat(intake.expires_at.replace("Z", "+00:00"))
        self.assertLess(deadline, expiry)
        later = (deadline + timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        reconciler = RuntimeInvestigationAdmissions(self.store, clock=lambda: later)
        expired = reconciler.reconcile_waiting(self.command_id)
        self.assertEqual(expired.status.value, "CAPACITY_EXPIRED")
        self.assertEqual(expired.version, 2)
        self.assertEqual(reconciler.reconcile_waiting(self.command_id), expired)

    def test_lost_response_and_restart_yield_one_intake(self):
        intent = self.aquila.outbox.get_by_mission(self.mission_id)
        mission = self.aquila.store.get_mission(self.mission_id)
        first = RuntimeInvestigationAdmissions(self.store).admit(intent, mission)
        self.assertEqual(self.aquila.outbox.get_by_mission(self.mission_id).status, "PENDING")
        self.store.close()
        self.store = new_runtime_store()
        replay_id = self.dispatcher().dispatch(self.command_id)
        self.assertEqual(replay_id, first.intake_id)
        self.assertEqual(self.dispatcher().dispatch(self.command_id), first.intake_id)
        self.assertEqual(self.aquila.outbox.get_by_mission(self.mission_id).status, "DELIVERED")
        self.assertEqual(self.store.get_investigation_by_mission(self.mission_id), first)

    def test_competing_dispatchers_admit_once(self):
        second_store = new_runtime_store()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(self.dispatcher(store).dispatch, self.command_id)
                           for store in (self.store, second_store)]
                ids = [future.result(timeout=10) for future in futures]
            self.assertEqual(ids[0], ids[1])
            self.assertEqual(self.store.get_investigation_by_mission(self.mission_id).intake_id, ids[0])
        finally:
            second_store.close()

    def test_forged_scope_and_replay_are_denied(self):
        intent = self.aquila.outbox.get_by_mission(self.mission_id)
        mission = self.aquila.store.get_mission(self.mission_id)
        admissions = RuntimeInvestigationAdmissions(self.store)
        with self.assertRaisesRegex(InvestigationAdmissionError, "INVESTIGATION_SCOPE_MISMATCH"):
            admissions.admit(replace(intent, organization_id=WORKSPACE), mission)
        self.assertIsNone(self.store.get_investigation_by_mission(self.mission_id))
        accepted = admissions.admit(intent, mission)
        self.assertEqual(admissions.admit(intent, mission), accepted)
        with self.assertRaisesRegex(InvestigationAdmissionError, "INVESTIGATION_REPLAY_CONFLICT"):
            admissions.admit(replace(intent, scout_grant_id="forged"), mission)

    def test_lost_ack_after_cancel_replays_existing_intake_only(self):
        intent = self.aquila.outbox.get_by_mission(self.mission_id)
        mission = self.aquila.store.get_mission(self.mission_id)
        accepted = RuntimeInvestigationAdmissions(self.store).admit(intent, mission)
        self.aquila.submit_command(actor=self.owner, mission_id=self.mission_id, body={
            "expected_version": 3, "idempotency_key": "cancel-after-intake",
            "command_type": "CANCEL", "payload": {},
        })
        self.assertEqual(self.dispatcher().dispatch(self.command_id), accepted.intake_id)
        self.assertEqual(self.aquila.outbox.get_by_mission(self.mission_id).status, "DELIVERED")
        self.assertEqual(self.store.get_investigation_by_mission(self.mission_id), accepted)

    def test_paused_delivery_retries_after_resume(self):
        self.aquila.submit_command(actor=self.owner, mission_id=self.mission_id, body={
            "expected_version": 3, "idempotency_key": "pause-before-intake",
            "command_type": "PAUSE", "payload": {},
        })
        self.assertEqual(self.dispatcher().dispatch_pending(), ())
        status = self.aquila.get_investigation(actor=self.owner, mission_id=self.mission_id)
        self.assertEqual(status.body["last_error_code"], "MISSION_NOT_ACTIVE")
        self.assertEqual(status.body["status"], "PENDING")
        self.assertEqual(self.dispatcher().pending(), ())
        self.assertIsNone(self.store.get_investigation_by_mission(self.mission_id))
        resumed = self.aquila.submit_command(actor=self.owner, mission_id=self.mission_id, body={
            "expected_version": 4, "idempotency_key": "resume-before-intake",
            "command_type": "RESUME", "payload": {},
        })
        self.assertEqual(resumed.status_code, 200)
        intake_id = self.dispatcher().dispatch(self.command_id)
        self.assertEqual(self.aquila.outbox.get_by_mission(self.mission_id).status, "DELIVERED")
        self.assertEqual(self.store.get_investigation_by_mission(self.mission_id).intake_id,
                         intake_id)

    def test_poisoned_correlation_blocks_only_its_own_delivery(self):
        second = self.aquila.create_mission(actor=self.owner, body={
            "organization_id": ORG, "workspace_id": WORKSPACE,
            "title": "Second investigation", "objective": "Which ADR covers Mission state?",
        })
        second_id = second.body["id"]
        self.aquila.submit_command(actor=self.owner, mission_id=second_id, body={
            "expected_version": 1, "idempotency_key": "start-second",
            "command_type": "START", "payload": {},
        })
        self.aquila.submit_command(actor=self.owner, mission_id=second_id, body={
            "expected_version": 2, "idempotency_key": "launch-second",
            "command_type": "REQUEST_INVESTIGATION", "payload": {"profile": PROFILE},
        })
        with self.aquila.store.transaction():
            self.aquila.store.connection.execute(
                "UPDATE investigation_outbox SET correlation_id = ? WHERE command_id = ?",
                ("x" * 37, self.command_id),
            )
        admitted = self.dispatcher().dispatch_pending()
        self.assertEqual(len(admitted), 1)
        self.assertEqual(self.aquila.outbox.get_by_mission(self.mission_id).status, "BLOCKED")
        self.assertEqual(self.aquila.outbox.get_by_mission(self.mission_id).last_error_code,
                         "INVALID_INVESTIGATION_INTENT")
        self.assertEqual(self.aquila.outbox.get_by_mission(second_id).status, "DELIVERED")

    def test_transient_outbox_retries_until_fixed_authority_expiry(self):
        for _ in range(8):
            with self.aquila.store.transaction():
                self.aquila.outbox.record_error(self.command_id, "DELIVERY_UNAVAILABLE")
            self.assertEqual(self.aquila.outbox.get_by_command(self.command_id).status,
                             "PENDING")
        with self.aquila.store.transaction():
            self.aquila.store.connection.execute(
                "UPDATE investigation_outbox SET expires_at = ? WHERE command_id = ?",
                ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
                 self.command_id),
            )
            self.aquila.outbox.record_error(self.command_id, "DELIVERY_UNAVAILABLE")
        self.assertEqual(self.aquila.outbox.get_by_command(self.command_id).status,
                         "BLOCKED")
        self.assertEqual(self.dispatcher().pending(), ())

    def test_cancel_and_grant_revocation_stop_undelivered_intake(self):
        self.aquila.submit_command(actor=self.owner, mission_id=self.mission_id, body={
            "expected_version": 3, "idempotency_key": "cancel", "command_type": "CANCEL", "payload": {},
        })
        with self.assertRaisesRegex(InvestigationDispatchError, "MISSION_TERMINAL"):
            self.dispatcher().dispatch(self.command_id)
        self.assertIsNone(self.store.get_investigation_by_mission(self.mission_id))


if __name__ == "__main__":
    unittest.main()
