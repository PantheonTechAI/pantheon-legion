import tempfile
import unittest
from pathlib import Path

import aquila_api
from aquila_api import AquilaService, PersistentAquilaService
from legion_cognition import InMemoryScoutRuntime
from legion_kernel import AuthorizationError, Principal, PrincipalType, RoeLevel


class DelegationGrantTests(unittest.TestCase):
    def setUp(self):
        self.owner = Principal(PrincipalType.HUMAN, "owner", frozenset({"MISSION_OWNER", "OPERATOR"}))
        self.operator = Principal(PrincipalType.HUMAN, "operator", frozenset({"OPERATOR"}))
        self.worker = Principal(PrincipalType.WORKLOAD, "worker", frozenset({"MISSION_WORKER"}))
        self.other_worker = Principal(PrincipalType.WORKLOAD, "other", frozenset({"MISSION_WORKER"}))

    def create_mission(self, service):
        response = service.create_mission(actor=self.owner, body={
            "organization_id": "11111111-1111-4111-8111-111111111111",
            "workspace_id": "22222222-2222-4222-8222-222222222222",
            "title": "Delegation boundary", "objective": "Prove grants are Aquila-owned.",
        })
        return response.body["id"]

    def issue(self, service, mission_id):
        return service.issue_delegation(
            issuer=self.owner, subject=self.worker, mission_id=mission_id,
            allowed_operations=frozenset({"READ_MISSION"}), roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )

    def scout(self, service, mission_id, worker, grant_id):
        return service.run_scout(
            mission_id=mission_id, scout=worker, delegation_id=grant_id,
            runtime=InMemoryScoutRuntime(), query="Read bounded context.",
            granted_capabilities=frozenset({"read.mission"}),
        )

    def test_only_aquila_issues_opaque_grant_ids(self):
        service = AquilaService()
        mission_id = self.create_mission(service)
        self.assertFalse(hasattr(aquila_api, "DelegationGrant"))
        with self.assertRaisesRegex(AuthorizationError, "MISSION_OWNER_REQUIRED"):
            service.issue_delegation(
                issuer=self.operator, subject=self.worker, mission_id=mission_id,
                allowed_operations=frozenset({"READ_MISSION"}), roe_ceiling=RoeLevel.OBSERVE,
                expires_at="9999-01-01T00:00:00Z",
            )
        events = service.kernel.timeline(mission_id)
        self.assertEqual(events[-1].event_type, "DELEGATION_ISSUANCE_DENIED")

    def test_unknown_or_wrong_subject_grant_fails_closed_and_is_audited(self):
        service = AquilaService()
        mission_id = self.create_mission(service)
        with self.assertRaisesRegex(AuthorizationError, "DELEGATION_INVALID"):
            self.scout(service, mission_id, self.worker, "forged-grant-id")
        grant_id = self.issue(service, mission_id)
        with self.assertRaisesRegex(AuthorizationError, "DELEGATION_SCOPE_MISMATCH"):
            self.scout(service, mission_id, self.other_worker, grant_id)
        evaluations = [event for event in service.kernel.timeline(mission_id) if event.event_type == "DELEGATION_EVALUATED"]
        self.assertEqual([(event.result, event.data["reason"]) for event in evaluations], [
            ("DENY", "DELEGATION_INVALID"), ("DENY", "DELEGATION_SCOPE_MISMATCH"),
        ])

    def test_revocation_survives_restart_and_prevents_future_use(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "aquila.sqlite3")
            service = PersistentAquilaService(database)
            mission_id = self.create_mission(service)
            grant_id = self.issue(service, mission_id)
            service.revoke_delegation(
                actor=self.owner, mission_id=mission_id, delegation_id=grant_id, reason="Worker retired."
            )
            service.close()

            restarted = PersistentAquilaService(database)
            with self.assertRaisesRegex(AuthorizationError, "DELEGATION_REVOKED"):
                self.scout(restarted, mission_id, self.worker, grant_id)
            events = restarted.kernel.timeline(mission_id)
            self.assertEqual([event.event_type for event in events[-2:]], [
                "DELEGATION_REVOKED", "DELEGATION_EVALUATED",
            ])
            restarted.close()


if __name__ == "__main__":
    unittest.main()
