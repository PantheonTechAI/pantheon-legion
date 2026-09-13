import tempfile
import unittest
from pathlib import Path

from legion_kernel import LegionKernel, Principal, PrincipalType, RoeLevel
from legion_store import DuplicateEvent, SQLiteMissionStore, StoreConflict


class SQLiteMissionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "aquila.sqlite3"
        self.store = SQLiteMissionStore(self.database)
        self.actor = Principal(
            PrincipalType.HUMAN,
            "owner",
            frozenset({"MISSION_OWNER", "OPERATOR"}),
        )
        self.kernel = LegionKernel()
        self.mission = self.kernel.create_mission(
            actor=self.actor,
            organization_id="org",
            workspace_id="workspace",
            title="Durability test",
            objective="Verify SQLite round-trip.",
            roe_level=RoeLevel.REVIEW,
        )

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_mission_round_trip_survives_reopen(self):
        self.store.save_mission(self.mission, expected_previous_version=None)
        self.store.close()
        reopened = SQLiteMissionStore(self.database)
        loaded = reopened.get_mission(self.mission.id)
        self.assertEqual(loaded.title, self.mission.title)
        self.assertEqual(loaded.version, 1)
        self.assertEqual(loaded.roe.level, RoeLevel.REVIEW)
        reopened.close()
        self.store = SQLiteMissionStore(self.database)

    def test_compare_and_swap_rejects_stale_snapshot(self):
        self.store.save_mission(self.mission, expected_previous_version=None)
        self.mission.version = 2
        self.store.save_mission(self.mission, expected_previous_version=1)
        stale = self.store.get_mission(self.mission.id)
        stale.version = 3
        with self.assertRaises(StoreConflict):
            self.store.save_mission(stale, expected_previous_version=1)
        self.assertEqual(self.store.get_mission(self.mission.id).version, 2)

    def test_audit_sequence_is_append_only_and_ordered(self):
        self.store.save_mission(self.mission, expected_previous_version=None)
        event = self.kernel.timeline(self.mission.id)[0]
        self.store.append_audit(event)
        self.assertEqual(self.store.get_audit(self.mission.id)[0].event_type, "MISSION_CREATED")
        with self.assertRaises(DuplicateEvent):
            self.store.append_audit(event)
        skipped = type(event)(
            id="event-2",
            sequence=3,
            mission_id=event.mission_id,
            mission_version=2,
            event_type="COMMAND_ACCEPTED",
            occurred_at=event.occurred_at,
            actor=event.actor,
            result="SUCCESS",
            correlation_id="correlation",
        )
        with self.assertRaises(DuplicateEvent):
            self.store.append_audit(skipped)

    def test_idempotency_record_round_trip(self):
        self.store.save_mission(self.mission, expected_previous_version=None)
        self.store.put_idempotency(
            mission_id=self.mission.id,
            idempotency_key="command-1",
            fingerprint="fingerprint",
            result={"status": "ACCEPTED", "version": 2},
        )
        self.assertEqual(
            self.store.get_idempotency(
                mission_id=self.mission.id,
                idempotency_key="command-1",
            ),
            {"fingerprint": "fingerprint", "result": {"status": "ACCEPTED", "version": 2}},
        )


if __name__ == "__main__":
    unittest.main()
