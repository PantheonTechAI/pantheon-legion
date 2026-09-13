import unittest

from aquila_api import AquilaService
from legion_kernel import LegionKernel, Principal, PrincipalType


class AquilaServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = AquilaService(LegionKernel())
        self.owner = Principal(
            PrincipalType.HUMAN,
            "owner",
            frozenset({"MISSION_OWNER", "OPERATOR"}),
        )
        self.operator = Principal(PrincipalType.HUMAN, "operator", frozenset({"OPERATOR"}))
        self.approver = Principal(PrincipalType.HUMAN, "approver", frozenset({"APPROVER"}))
        self.observer = Principal(PrincipalType.HUMAN, "observer", frozenset({"OBSERVER"}))
        created = self.service.create_mission(
            actor=self.owner,
            body={
                "organization_id": "11111111-1111-4111-8111-111111111111",
                "workspace_id": "22222222-2222-4222-8222-222222222222",
                "title": "API test Mission",
                "objective": "Exercise the Aquila service boundary.",
                "initial_roe_level": "REVIEW",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.mission_id = created.body["id"]

    def command(self, actor, version, key, command_type, payload):
        return self.service.submit_command(
            actor=actor,
            mission_id=self.mission_id,
            body={
                "expected_version": version,
                "idempotency_key": key,
                "command_type": command_type,
                "payload": payload,
            },
        )

    def test_create_read_and_stale_command_error_mapping(self):
        started = self.command(self.owner, 1, "start", "START", {})
        self.assertEqual(started.status_code, 200)
        added = self.command(
            self.operator,
            2,
            "constraint",
            "ADD_CONSTRAINT",
            {
                "constraint": {
                    "id": "constraint-1",
                    "text": "Keep evidence.",
                    "severity": "REQUIRED",
                }
            },
        )
        self.assertEqual(added.status_code, 200)
        stale = self.command(
            self.owner,
            2,
            "stale",
            "UPDATE_OBJECTIVE",
            {"objective": "stale"},
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.body["code"], "VERSION_CONFLICT")
        read = self.service.get_mission(actor=self.observer, mission_id=self.mission_id)
        self.assertEqual(read.status_code, 200)
        self.assertEqual(read.body["version"], 3)

    def test_approval_request_and_decision_are_openapi_shaped(self):
        self.command(self.owner, 1, "start", "START", {})
        requested = self.command(
            self.owner,
            2,
            "action",
            "REQUEST_ACTION",
            {
                "action_id": "33333333-3333-4333-8333-333333333333",
                "capability": "test.mutation",
                "arguments": {"target": "resource"},
                "target": "resource",
                "side_effect_class": "MUTATION",
            },
        )
        self.assertEqual(requested.status_code, 202)
        approval = self.service.decide_approval(
            actor=self.approver,
            mission_id=self.mission_id,
            body={
                "approval_id": requested.body["approval_id"],
                "expected_mission_version": 3,
                "decision": "APPROVE",
                "reason": "Reviewed.",
            },
        )
        self.assertEqual(approval.status_code, 200)
        self.assertEqual(approval.body["status"], "APPROVED")
        self.assertEqual(approval.body["scope"]["capability"], "test.mutation")

    def test_unauthorized_reader_and_command_are_denied(self):
        unknown = Principal(PrincipalType.HUMAN, "unknown", frozenset())
        denied_read = self.service.get_mission(actor=unknown, mission_id=self.mission_id)
        self.assertEqual(denied_read.status_code, 403)
        self.assertEqual(denied_read.body["code"], "READ_ROLE_REQUIRED")

        self.command(self.owner, 1, "start", "START", {})
        denied = self.command(
            self.observer,
            2,
            "observer-roe",
            "SET_ROE",
            {"level": "BOUNDED_AUTONOMOUS", "reason": "not allowed"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.body["code"], "OPERATOR_ROLE_REQUIRED")
        timeline = self.service.get_timeline(
            actor=self.observer,
            mission_id=self.mission_id,
            limit=1,
        )
        self.assertEqual(timeline.status_code, 200)
        self.assertTrue(timeline.body["has_more"])
        self.assertEqual(len(timeline.body["events"]), 1)

    def test_cancel_uses_command_semantics(self):
        self.command(self.owner, 1, "start", "START", {})
        cancelled = self.service.cancel_mission(
            actor=self.owner,
            mission_id=self.mission_id,
            body={
                "expected_version": 2,
                "idempotency_key": "cancel",
                "reason": "Test complete.",
            },
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.body["status"], "CANCELLED")

    def test_authorization_engine_enforces_owner_only_autonomy_elevation(self):
        self.command(self.owner, 1, "start", "START", {})
        denied = self.command(
            self.operator,
            2,
            "operator-roe",
            "SET_ROE",
            {"level": "BOUNDED_AUTONOMOUS", "reason": "operator cannot elevate autonomy"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.body["code"], "OWNER_REQUIRED_FOR_AUTONOMY")
        self.assertEqual(
            self.service.get_mission(actor=self.owner, mission_id=self.mission_id).body["version"],
            2,
        )

    def test_authorization_engine_allows_pending_review_action_request(self):
        self.command(self.owner, 1, "start", "START", {})
        requested = self.command(
            self.operator,
            2,
            "operator-action",
            "REQUEST_ACTION",
            {
                "action_id": "44444444-4444-4444-8444-444444444444",
                "capability": "test.mutation",
                "arguments": {},
                "target": "resource",
                "side_effect_class": "MUTATION",
            },
        )
        self.assertEqual(requested.status_code, 202)


if __name__ == "__main__":
    unittest.main()
