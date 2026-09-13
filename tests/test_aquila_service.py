import unittest

from aquila_api import AquilaService, DelegationGrant
from legion_kernel import AuthorizationError, LegionKernel, Principal, PrincipalType, RoeLevel


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
        self.worker = Principal(PrincipalType.WORKLOAD, "worker", frozenset({"MISSION_WORKER"}))
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

    def test_participants_are_exposed_in_the_mission_projection(self):
        added = self.command(
            self.owner,
            1,
            "add-approver",
            "ADD_PARTICIPANT",
            {"participant": {
                "principal": {"type": "HUMAN", "subject": "approver"},
                "role": "APPROVER", "scope": "production",
            }},
        )
        self.assertEqual(added.status_code, 200)
        mission = self.service.get_mission(actor=self.owner, mission_id=self.mission_id)
        self.assertEqual(mission.body["participants"], [{
            "principal": {"type": "HUMAN", "subject": "approver"},
            "role": "APPROVER",
            "scope": "production",
        }])

    def test_unknown_command_type_is_rejected_without_a_version_change(self):
        rejected = self.command(self.owner, 1, "unsupported", "DELETE_MISSION", {})
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(rejected.body["code"], "UNKNOWN_COMMAND_TYPE")
        self.assertEqual(rejected.body["current_version"], 1)

    def test_missing_constraint_removal_is_rejected_without_a_version_change(self):
        rejected = self.command(
            self.owner,
            1,
            "remove-missing-constraint",
            "REMOVE_CONSTRAINT",
            {"constraint_id": "missing"},
        )
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(rejected.body["code"], "CONSTRAINT_NOT_FOUND")
        self.assertEqual(rejected.body["current_version"], 1)

    def test_unexpected_command_payload_field_is_rejected_without_a_version_change(self):
        rejected = self.command(self.owner, 1, "invalid-payload", "START", {"unexpected": True})
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(rejected.body["code"], "INVALID_COMMAND_PAYLOAD")
        self.assertEqual(rejected.body["current_version"], 1)

    def test_missing_roe_level_is_rejected_as_an_invalid_payload(self):
        rejected = self.command(self.owner, 1, "missing-roe-level", "SET_ROE", {"reason": "missing level"})
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(rejected.body["code"], "INVALID_COMMAND_PAYLOAD")

    def test_schema_invalid_roe_payload_is_rejected_without_a_version_change(self):
        rejected = self.command(self.owner, 1, "duplicate-capability", "SET_ROE", {"level": "REVIEW", "reason": "duplicate", "allowed_capabilities": ["test.read", "test.read"]})
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(rejected.body["code"], "INVALID_COMMAND_PAYLOAD")
        self.assertEqual(rejected.body["current_version"], 1)

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
        denied = self.service.decide_approval(
            actor=self.observer,
            mission_id=self.mission_id,
            body={
                "approval_id": requested.body["approval_id"],
                "expected_mission_version": 3,
                "decision": "APPROVE",
                "reason": "Unauthorized approval.",
            },
        )
        self.assertEqual(denied.status_code, 403)
        denied_authorization = self.service.kernel.timeline(self.mission_id)[-1]
        self.assertEqual(denied_authorization.event_type, "AUTHORIZATION_EVALUATED")
        self.assertEqual(denied_authorization.result, "DENY")
        self.assertEqual(denied_authorization.data["operation"], "DECIDE_APPROVAL")
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
        authorization = self.service.kernel.timeline(self.mission_id)[-2]
        self.assertEqual(authorization.event_type, "AUTHORIZATION_EVALUATED")
        self.assertEqual(authorization.result, "ALLOW")
        self.assertEqual(authorization.data["operation"], "DECIDE_APPROVAL")
        self.assertTrue(authorization.data["decision_id"])

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
        authorization = self.service.kernel.timeline(self.mission_id)[-1]
        self.assertEqual(authorization.event_type, "AUTHORIZATION_EVALUATED")
        self.assertEqual(authorization.result, "DENY")
        self.assertEqual(authorization.data["reason"], "OPERATOR_ROLE_REQUIRED")
        self.assertTrue(authorization.data["decision_id"])
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

    def test_paused_mission_does_not_start_a_durable_execution(self):
        self.command(self.owner, 1, "start", "START", {})
        requested = self.command(
            self.owner,
            2,
            "read-action",
            "REQUEST_ACTION",
            {
                "action_id": "55555555-5555-4555-8555-555555555555",
                "capability": "test.read",
                "arguments": {},
                "target": "resource",
                "side_effect_class": "READ",
            },
        )
        self.assertEqual(requested.status_code, 200)
        self.command(self.owner, 3, "pause", "PAUSE", {})
        with self.assertRaisesRegex(AuthorizationError, "MISSION_PAUSED"):
            self.service.execute_action(
                mission_id=self.mission_id,
                action_id="55555555-5555-4555-8555-555555555555",
                worker=self.owner,
            )
        self.assertEqual(self.service.action_executions, {})
        self.assertEqual(self.service.execution.records, {})

    def test_suspend_stops_execution_until_an_operator_resumes(self):
        self.command(self.owner, 1, "start", "START", {})
        requested = self.command(
            self.owner,
            2,
            "read-action",
            "REQUEST_ACTION",
            {
                "action_id": "77777777-7777-4777-8777-777777777777",
                "capability": "test.read",
                "arguments": {},
                "target": "resource",
                "side_effect_class": "READ",
            },
        )
        self.assertEqual(requested.status_code, 200)
        suspended = self.command(
            self.operator,
            3,
            "suspend",
            "SUSPEND",
            {"reason": "Safety review."},
        )
        self.assertEqual(suspended.status_code, 200)
        self.assertEqual(suspended.body["mission_version"], 4)
        self.assertEqual(self.service.kernel.timeline(self.mission_id)[-1].data["reason"], "Safety review.")
        with self.assertRaisesRegex(AuthorizationError, "MISSION_SUSPENDED"):
            self.service.execute_action(
                mission_id=self.mission_id,
                action_id="77777777-7777-4777-8777-777777777777",
                worker=self.owner,
            )
        resumed = self.command(self.operator, 4, "resume", "RESUME", {})
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.body["mission_version"], 5)
        self.assertEqual(
            self.service.execute_action(
                mission_id=self.mission_id,
                action_id="77777777-7777-4777-8777-777777777777",
                worker=self.owner,
            ),
            "EXECUTED",
        )

    def test_suspend_requires_a_reason(self):
        self.command(self.owner, 1, "start", "START", {})
        rejected = self.command(self.operator, 2, "suspend", "SUSPEND", {})
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(rejected.body["code"], "SUSPENSION_REASON_REQUIRED")
        self.assertEqual(self.service.get_mission(actor=self.owner, mission_id=self.mission_id).body["status"], "ACTIVE")

    def test_workload_execution_requires_a_bounded_delegation(self):
        self.command(self.owner, 1, "start", "START", {})
        requested = self.command(
            self.owner,
            2,
            "read-action",
            "REQUEST_ACTION",
            {
                "action_id": "66666666-6666-4666-8666-666666666666",
                "capability": "test.read",
                "arguments": {},
                "target": "resource",
                "side_effect_class": "READ",
            },
        )
        self.assertEqual(requested.status_code, 200)
        with self.assertRaisesRegex(AuthorizationError, "DELEGATION_REQUIRED"):
            self.service.execute_action(
                mission_id=self.mission_id,
                action_id="66666666-6666-4666-8666-666666666666",
                worker=self.worker,
            )
        self.assertEqual(self.service.action_executions, {})
        self.assertEqual(self.service.kernel.side_effects, {})
        events = self.service.kernel.timeline(self.mission_id)
        self.assertEqual(events[-2].event_type, "AUTHORIZATION_EVALUATED")
        self.assertEqual(events[-2].result, "DENY")
        self.assertEqual(events[-2].data["reason"], "DELEGATION_REQUIRED")
        self.assertEqual(events[-2].data["policy_version"], "mvp-1")
        self.assertTrue(events[-2].data["decision_id"])
        self.assertEqual(events[-1].data["error_code"], "DELEGATION_REQUIRED")

        grant = DelegationGrant(
            grant_id="worker-read-grant",
            issuer=self.owner,
            subject=self.worker,
            mission_id=self.mission_id,
            allowed_operations=frozenset({"EXECUTE_ACTION"}),
            roe_ceiling=RoeLevel.REVIEW,
            expires_at="9999-01-01T00:00:00Z",
        )
        self.assertEqual(
            self.service.execute_action(
                mission_id=self.mission_id,
                action_id="66666666-6666-4666-8666-666666666666",
                worker=self.worker,
                delegation=grant,
            ),
            "EXECUTED",
        )


if __name__ == "__main__":
    unittest.main()
