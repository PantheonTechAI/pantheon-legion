import unittest

from legion_kernel import (
    AuthorizationError,
    LegionKernel,
    Principal,
    PrincipalType,
    RoeLevel,
    WorkerKilled,
)


class DomainKernelTests(unittest.TestCase):
    def setUp(self):
        self.kernel = LegionKernel()
        self.user_a = Principal(PrincipalType.HUMAN, "user-a", frozenset({"MISSION_OWNER", "OPERATOR"}))
        self.user_b = Principal(PrincipalType.HUMAN, "user-b", frozenset({"OPERATOR"}))
        self.approver = Principal(PrincipalType.HUMAN, "approver", frozenset({"APPROVER"}))
        self.observer = Principal(PrincipalType.HUMAN, "observer", frozenset({"OBSERVER"}))
        self.worker = Principal(PrincipalType.WORKLOAD, "worker", frozenset({"MISSION_WORKER"}))
        self.mission = self.kernel.create_mission(
            actor=self.user_a,
            organization_id="org",
            workspace_id="workspace",
            title="Acceptance Mission",
            objective="Prove the Mission kernel.",
            roe_level=RoeLevel.REVIEW,
        )

    def start(self):
        return self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.user_a,
            expected_version=1,
            idempotency_key="start",
            command_type="START",
            payload={},
        )

    def request_mutation(self):
        return self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.user_a,
            expected_version=2,
            idempotency_key="request-mutation",
            command_type="REQUEST_ACTION",
            payload={
                "action_id": "action-1",
                "capability": "test.bounded_mutation",
                "arguments": {"target": "resource"},
                "target": "resource",
                "side_effect_class": "MUTATION",
            },
        )

    def test_two_users_share_mission_and_stale_command_is_rejected(self):
        self.assertEqual(self.start().mission_version, 2)
        accepted = self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.user_b,
            expected_version=2,
            idempotency_key="constraint",
            command_type="ADD_CONSTRAINT",
            payload={
                "constraint": {
                    "id": "constraint-1",
                    "text": "Preserve evidence.",
                    "severity": "REQUIRED",
                }
            },
        )
        self.assertEqual(accepted.status, "ACCEPTED")
        stale = self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.user_a,
            expected_version=2,
            idempotency_key="stale-objective",
            command_type="UPDATE_OBJECTIVE",
            payload={"objective": "Must not overwrite"},
        )
        self.assertEqual(stale.error_code, "VERSION_CONFLICT")
        self.assertEqual(self.kernel.get_mission(self.mission.id).version, 3)
        self.assertTrue(any(e.result == "REJECTED" for e in self.kernel.audit_events(self.mission.id)))

    def test_unauthorized_principal_fails_closed(self):
        self.start()
        result = self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.observer,
            expected_version=2,
            idempotency_key="observer-roe",
            command_type="SET_ROE",
            payload={"level": "BOUNDED_AUTONOMOUS", "reason": "not allowed"},
        )
        self.assertEqual(result.error_code, "FORBIDDEN")
        self.assertEqual(self.kernel.get_mission(self.mission.id).version, 2)
        self.request_mutation()
        with self.assertRaises(AuthorizationError) as error:
            self.kernel.execute_action(
                mission_id=self.mission.id,
                action_id="action-1",
                worker=self.observer,
            )
        self.assertEqual(str(error.exception), "FORBIDDEN")

    def test_roe_narrowing_invalidates_approval(self):
        self.start()
        requested = self.request_mutation()
        self.assertEqual(requested.status, "AWAITING_APPROVAL")
        approval = self.kernel.decide_approval(
            approval_id=requested.approval_id,
            approver=self.approver,
            expected_mission_version=3,
            decision="APPROVE",
            reason="Approved for current scope.",
        )
        self.assertEqual(approval.status, "APPROVED")
        narrowed = self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.user_a,
            expected_version=3,
            idempotency_key="narrow-roe",
            command_type="SET_ROE",
            payload={"level": "OBSERVE", "reason": "Review evidence first."},
        )
        self.assertEqual(narrowed.status, "ACCEPTED")
        with self.assertRaises(AuthorizationError) as error:
            self.kernel.execute_action(
                mission_id=self.mission.id,
                action_id="action-1",
                worker=self.worker,
            )
        self.assertEqual(str(error.exception), "APPROVAL_STALE")
        self.assertEqual(self.kernel.side_effects, {})

    def test_worker_restart_does_not_duplicate_side_effect(self):
        self.start()
        requested = self.request_mutation()
        self.kernel.decide_approval(
            approval_id=requested.approval_id,
            approver=self.approver,
            expected_mission_version=3,
            decision="APPROVE",
            reason="Recovery test approval.",
        )
        with self.assertRaises(WorkerKilled):
            self.kernel.execute_action(
                mission_id=self.mission.id,
                action_id="action-1",
                worker=self.worker,
                fail_after_side_effect=True,
            )
        self.assertEqual(self.kernel.side_effects["action-1"], 1)
        self.assertEqual(
            self.kernel.execute_action(
                mission_id=self.mission.id,
                action_id="action-1",
                worker=self.worker,
            ),
            "RECOVERED",
        )
        self.assertEqual(self.kernel.side_effects["action-1"], 1)

    def test_paused_mission_rejects_execution_before_side_effect(self):
        self.start()
        requested = self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.user_a,
            expected_version=2,
            idempotency_key="request-read",
            command_type="REQUEST_ACTION",
            payload={
                "action_id": "read-action",
                "capability": "test.read",
                "arguments": {},
                "target": "resource",
                "side_effect_class": "READ",
            },
        )
        self.assertEqual(requested.status, "ACCEPTED")
        self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.user_a,
            expected_version=3,
            idempotency_key="pause",
            command_type="PAUSE",
            payload={},
        )
        with self.assertRaisesRegex(AuthorizationError, "MISSION_PAUSED"):
            self.kernel.execute_action(
                mission_id=self.mission.id,
                action_id="read-action",
                worker=self.worker,
            )
        self.assertEqual(self.kernel.side_effects, {})
        self.assertEqual(self.kernel.timeline(self.mission.id)[-1].event_type, "EXECUTION_REJECTED")

    def test_expired_approval_rejects_execution_before_side_effect(self):
        self.start()
        requested = self.request_mutation()
        approval = self.kernel.decide_approval(
            approval_id=requested.approval_id,
            approver=self.approver,
            expected_mission_version=3,
            decision="APPROVE",
            reason="Approval that will expire.",
        )
        self.kernel.approvals[approval.id].expires_at = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(AuthorizationError, "APPROVAL_STALE"):
            self.kernel.execute_action(
                mission_id=self.mission.id,
                action_id="action-1",
                worker=self.worker,
            )
        self.assertEqual(self.kernel.side_effects, {})
        self.assertEqual(self.kernel.approvals[approval.id].status, "EXPIRED")
        self.assertEqual(self.kernel.timeline(self.mission.id)[-2].event_type, "APPROVAL_EXPIRED")

    def test_expired_pending_approval_cannot_be_decided(self):
        self.start()
        requested = self.request_mutation()
        self.kernel.approvals[requested.approval_id].expires_at = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(AuthorizationError, "APPROVAL_STALE"):
            self.kernel.decide_approval(
                approval_id=requested.approval_id,
                approver=self.approver,
                expected_mission_version=3,
                decision="APPROVE",
                reason="Too late.",
            )
        self.assertEqual(self.kernel.approvals[requested.approval_id].status, "EXPIRED")
        self.assertEqual(self.kernel.timeline(self.mission.id)[-1].event_type, "APPROVAL_EXPIRED")

    def test_audit_reconstructs_accepted_and_rejected_changes(self):
        self.start()
        self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.user_b,
            expected_version=2,
            idempotency_key="constraint",
            command_type="ADD_CONSTRAINT",
            payload={
                "constraint": {
                    "id": "constraint-1",
                    "text": "Preserve evidence.",
                    "severity": "PROHIBITED",
                }
            },
        )
        self.kernel.submit_command(
            mission_id=self.mission.id,
            actor=self.user_a,
            expected_version=2,
            idempotency_key="stale-pause",
            command_type="PAUSE",
            payload={},
        )
        events = self.kernel.timeline(self.mission.id)
        self.assertEqual([event.sequence for event in events], list(range(1, len(events) + 1)))
        self.assertEqual(events[0].event_type, "MISSION_CREATED")
        self.assertTrue(any(event.event_type == "COMMAND_REJECTED" for event in events))
        accepted_versions = [event.mission_version for event in events if event.result == "SUCCESS"]
        self.assertEqual(accepted_versions[:3], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
