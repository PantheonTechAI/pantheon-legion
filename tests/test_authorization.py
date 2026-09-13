import unittest

from aquila_api.authorization import (
    AuthorizationEngine,
    AuthorizationRequest,
    Decision,
    DelegationGrant,
)
from legion_kernel import MissionStatus, Principal, PrincipalType, RoeLevel


class AuthorizationEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = AuthorizationEngine()
        self.owner = Principal(PrincipalType.HUMAN, "owner", frozenset({"MISSION_OWNER", "OPERATOR"}))
        self.operator = Principal(PrincipalType.HUMAN, "operator", frozenset({"OPERATOR"}))
        self.observer = Principal(PrincipalType.HUMAN, "observer", frozenset({"OBSERVER"}))
        self.approver = Principal(PrincipalType.HUMAN, "approver", frozenset({"APPROVER"}))
        self.worker = Principal(PrincipalType.WORKLOAD, "worker", frozenset({"MISSION_WORKER"}))

    def request(self, principal, operation, **kwargs):
        return AuthorizationRequest(
            principal=principal,
            mission_id="mission-1",
            operation=operation,
            roe_level=kwargs.pop("roe_level", RoeLevel.REVIEW),
            mission_status=kwargs.pop("mission_status", MissionStatus.ACTIVE),
            **kwargs,
        )

    def test_read_is_allowed_to_observer_but_mutation_is_not(self):
        self.assertEqual(self.engine.decide(self.request(self.observer, "READ_MISSION")).decision, Decision.ALLOW)
        denied = self.engine.decide(
            self.request(self.observer, "SUBMIT_COMMAND", side_effect_class="MUTATION", capability="restart")
        )
        self.assertEqual(denied.decision, Decision.DENY)
        self.assertEqual(denied.reason, "OPERATOR_ROLE_REQUIRED")

    def test_roe_and_approval_are_enforced(self):
        denied = self.engine.decide(
            self.request(self.operator, "EXECUTE_ACTION", side_effect_class="MUTATION", capability="restart", roe_level=RoeLevel.REVIEW)
        )
        self.assertEqual(denied.reason, "APPROVAL_REQUIRED")
        allowed = self.engine.decide(
            self.request(self.operator, "EXECUTE_ACTION", side_effect_class="MUTATION", capability="restart", roe_level=RoeLevel.REVIEW, approval_present=True)
        )
        self.assertEqual(allowed.decision, Decision.ALLOW)
        self.assertEqual(allowed.policy_version, "mvp-1")

    def test_autonomy_elevation_requires_owner(self):
        operator = self.engine.decide(
            self.request(self.operator, "SET_ROE", roe_level=RoeLevel.BOUNDED_AUTONOMOUS, side_effect_class="READ")
        )
        self.assertEqual(operator.reason, "OWNER_REQUIRED_FOR_AUTONOMY")
        owner = self.engine.decide(
            self.request(self.owner, "SET_ROE", roe_level=RoeLevel.BOUNDED_AUTONOMOUS, side_effect_class="READ")
        )
        self.assertEqual(owner.decision, Decision.ALLOW)

    def test_workload_requires_bounded_delegation(self):
        request = self.request(self.worker, "EXECUTE_ACTION", side_effect_class="MUTATION", capability="restart", approval_present=True)
        self.assertEqual(self.engine.decide(request).reason, "DELEGATION_REQUIRED")
        grant = DelegationGrant(
            grant_id="grant-1",
            issuer=self.owner,
            subject=self.worker,
            mission_id="mission-1",
            allowed_operations=frozenset({"EXECUTE_ACTION"}),
            roe_ceiling=RoeLevel.REVIEW,
            expires_at="9999-01-01T00:00:00Z",
        )
        allowed = self.engine.decide(AuthorizationRequest(**{**request.__dict__, "delegation": grant}))
        self.assertEqual(allowed.decision, Decision.ALLOW)

    def test_expired_or_revoked_delegation_fails_closed(self):
        base = dict(
            grant_id="grant-1",
            issuer=self.owner,
            subject=self.worker,
            mission_id="mission-1",
            allowed_operations=frozenset({"READ_MISSION"}),
            roe_ceiling=RoeLevel.OBSERVE,
            expires_at="2000-01-01T00:00:00Z",
        )
        request = self.request(self.worker, "READ_MISSION", delegation=DelegationGrant(**base))
        self.assertEqual(self.engine.decide(request).reason, "DELEGATION_EXPIRED")
        revoked = DelegationGrant(**{**base, "expires_at": "9999-01-01T00:00:00Z", "revoked": True})
        self.assertEqual(self.engine.decide(self.request(self.worker, "READ_MISSION", delegation=revoked)).reason, "DELEGATION_REVOKED")

    def test_terminal_mission_denies_non_read_operations(self):
        decision = self.engine.decide(
            self.request(self.owner, "SUBMIT_COMMAND", mission_status=MissionStatus.CANCELLED, side_effect_class="READ")
        )
        self.assertEqual(decision.reason, "MISSION_TERMINAL")
