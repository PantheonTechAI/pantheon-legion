import sqlite3
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aquila_api import (
    AquilaService,
    InProcessAquilaAgentAuthority,
    InProcessAquilaKnowledgeAuthority,
    PersistentAquilaService,
)
from legion_kernel import LegionKernel, Principal, PrincipalType, RoeLevel
from legion_runtime import (
    ActorRef,
    AgentIdentity,
    AgentRole,
    AgentStatus,
    AuthorityDenied,
    AuthorityUnavailable,
    GroundedEvidenceReadRequest,
)
from legion_tabula import ScopeBinding
from pantheon_sts import (
    Ed25519AssertionVerifier,
    InMemorySecurityTokenService,
    sign_assertion,
)


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
AGENT_ID = "33333333-3333-4333-8333-333333333333"
ASSIGNMENT_ID = "44444444-4444-4444-8444-444444444444"
BINDING_ID = "55555555-5555-4555-8555-555555555555"
CORRELATION = "66666666-6666-4666-8666-666666666666"


class AquilaAgentAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.owner = Principal(
            PrincipalType.HUMAN,
            "owner",
            frozenset({"MISSION_OWNER", "OPERATOR"}),
        )
        self.observer = Principal(
            PrincipalType.HUMAN, "observer", frozenset({"OBSERVER"})
        )
        self.worker = Principal(PrincipalType.WORKLOAD, "runtime-workload")
        self.agent = AgentIdentity(
            agent_id=AGENT_ID,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="First Centurion",
            role=AgentRole.CENTURION,
            status=AgentStatus.ACTIVE,
            version=1,
            created_by=ActorRef("HUMAN", "owner"),
            created_at="2026-09-17T00:00:00Z",
            updated_at="2026-09-17T00:00:00Z",
        )

    def create_mission(self, service):
        response = service.create_mission(
            actor=self.owner,
            body={
                "organization_id": ORG,
                "workspace_id": WORKSPACE,
                "title": "Persistent Centurion",
                "objective": "Prove durable organizational identity.",
            },
        )
        return response.body["id"]

    def test_assignment_has_dedicated_policy_and_audit_without_mission_mutation(self):
        service = AquilaService(LegionKernel())
        mission_id = self.create_mission(service)
        adapter = InProcessAquilaAgentAuthority(service)
        view = adapter.authorize_assignment(
            actor=self.owner,
            agent=self.agent,
            assignment_id=ASSIGNMENT_ID,
            mission_id=mission_id,
            correlation_id=CORRELATION,
        )
        self.assertEqual(view.mission_version, 1)
        self.assertEqual(service.kernel.get_mission(mission_id).version, 1)
        event = service.kernel.timeline(mission_id)[-1]
        self.assertEqual(event.event_type, "AGENT_ASSIGNMENT_AUTHORIZATION_EVALUATED")
        self.assertEqual(event.data["assignment_id"], ASSIGNMENT_ID)
        self.assertEqual(event.result, "ALLOW")
        with self.assertRaisesRegex(AuthorityDenied, "OPERATOR_ROLE_REQUIRED"):
            adapter.authorize_assignment(
                actor=self.observer,
                agent=self.agent,
                assignment_id="77777777-7777-4777-8777-777777777777",
                mission_id=mission_id,
                correlation_id=CORRELATION,
            )
        with self.assertRaisesRegex(AuthorityDenied, "OPERATOR_ROLE_REQUIRED"):
            adapter.authorize_assignment(
                actor=self.worker,
                agent=self.agent,
                assignment_id="88888888-8888-4888-8888-888888888888",
                mission_id=mission_id,
                correlation_id=CORRELATION,
            )

    def test_resume_requires_current_bounded_workload_grant(self):
        service = AquilaService(LegionKernel())
        mission_id = self.create_mission(service)
        adapter = InProcessAquilaAgentAuthority(service)
        grant_id = service.issue_delegation(
            issuer=self.owner,
            subject=self.worker,
            mission_id=mission_id,
            allowed_operations=frozenset({"READ_MISSION"}),
            roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )
        view = adapter.authorize_resume(
            workload=self.worker,
            delegation_id=grant_id,
            agent_id=AGENT_ID,
            assignment_id=ASSIGNMENT_ID,
            mission_id=mission_id,
            binding_id=BINDING_ID,
            correlation_id=CORRELATION,
        )
        self.assertEqual(view.mission_id, mission_id)
        event = service.kernel.timeline(mission_id)[-1]
        self.assertEqual(event.event_type, "AGENT_RUNTIME_AUTHORIZATION_EVALUATED")
        self.assertEqual(event.data["grant_id"], grant_id)
        self.assertFalse(
            any(
                item.event_type == "DELEGATION_EVALUATED"
                and item.data.get("operation") == "READ_MISSION"
                for item in service.kernel.timeline(mission_id)
            )
        )
        service.revoke_delegation(
            actor=self.owner,
            mission_id=mission_id,
            delegation_id=grant_id,
            reason="End Runtime access.",
        )
        with self.assertRaisesRegex(AuthorityDenied, "DELEGATION_REVOKED"):
            adapter.authorize_resume(
                workload=self.worker,
                delegation_id=grant_id,
                agent_id=AGENT_ID,
                assignment_id=ASSIGNMENT_ID,
                mission_id=mission_id,
                binding_id="88888888-8888-4888-8888-888888888888",
                correlation_id=CORRELATION,
            )


    def test_scout_context_is_fresh_bounded_and_correlated(self):
        service = AquilaService(LegionKernel())
        mission_id = self.create_mission(service)
        adapter = InProcessAquilaAgentAuthority(service)
        grant_id = service.issue_delegation(
            issuer=self.owner,
            subject=self.worker,
            mission_id=mission_id,
            allowed_operations=frozenset({"READ_MISSION"}),
            roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )
        work_item_id = "77777777-7777-4777-8777-777777777777"
        attempt_id = "88888888-8888-4888-8888-888888888888"
        context = adapter.authorize_and_read(
            workload=self.worker,
            delegation_id=grant_id,
            agent_id=AGENT_ID,
            assignment_id=ASSIGNMENT_ID,
            work_item_id=work_item_id,
            attempt_id=attempt_id,
            mission_id=mission_id,
            correlation_id=CORRELATION,
        )
        self.assertEqual(context.mission_id, mission_id)
        self.assertEqual(context.title, "Persistent Centurion")
        self.assertEqual(context.objective, "Prove durable organizational identity.")
        event = service.kernel.timeline(mission_id)[-1]
        self.assertEqual(
            event.event_type, "SCOUT_MISSION_CONTEXT_AUTHORIZATION_EVALUATED"
        )
        self.assertEqual(event.data["work_item_id"], work_item_id)
        self.assertEqual(event.data["attempt_id"], attempt_id)
        self.assertNotIn("objective", event.data)
        service.revoke_delegation(
            actor=self.owner,
            mission_id=mission_id,
            delegation_id=grant_id,
            reason="End Scout read.",
        )
        with self.assertRaisesRegex(AuthorityDenied, "DELEGATION_REVOKED"):
            adapter.authorize_and_read(
                workload=self.worker,
                delegation_id=grant_id,
                agent_id=AGENT_ID,
                assignment_id=ASSIGNMENT_ID,
                work_item_id=work_item_id,
                attempt_id=attempt_id,
                mission_id=mission_id,
                correlation_id=CORRELATION,
            )
    def test_persistent_aquila_keeps_agent_authority_facts_only(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "aquila.sqlite3")
            service = PersistentAquilaService(database)
            mission_id = self.create_mission(service)
            adapter = InProcessAquilaAgentAuthority(service)
            adapter.authorize_assignment(
                actor=self.owner,
                agent=self.agent,
                assignment_id=ASSIGNMENT_ID,
                mission_id=mission_id,
                correlation_id=CORRELATION,
            )
            service.close()
            reopened = PersistentAquilaService(database)
            events = reopened.kernel.timeline(mission_id)
            self.assertTrue(
                any(
                    event.event_type
                    == "AGENT_ASSIGNMENT_AUTHORIZATION_EVALUATED"
                    for event in events
                )
            )
            tables = {
                row[0]
                for row in reopened.store.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertNotIn("agents", tables)
            self.assertNotIn("coordination_checkpoints", tables)
            self.assertEqual(reopened.kernel.get_mission(mission_id).version, 1)
            reopened.close()

    def test_persistent_store_failure_is_translated_to_authority_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            service = PersistentAquilaService(
                str(Path(directory) / "aquila.sqlite3")
            )
            mission_id = self.create_mission(service)
            adapter = InProcessAquilaAgentAuthority(service)
            service.close()

            with self.assertRaises(AuthorityUnavailable) as caught:
                adapter.authorize_assignment(
                    actor=self.owner,
                    agent=self.agent,
                    assignment_id=ASSIGNMENT_ID,
                    mission_id=mission_id,
                    correlation_id=CORRELATION,
                )

            self.assertIsInstance(caught.exception.__cause__, sqlite3.Error)

    def test_terminal_mission_denies_assignment_and_resume(self):
        service = AquilaService(LegionKernel())
        mission_id = self.create_mission(service)
        adapter = InProcessAquilaAgentAuthority(service)
        grant_id = service.issue_delegation(
            issuer=self.owner,
            subject=self.worker,
            mission_id=mission_id,
            allowed_operations=frozenset({"READ_MISSION"}),
            roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )
        cancelled = service.submit_command(
            actor=self.owner,
            mission_id=mission_id,
            body={
                "expected_version": 1,
                "idempotency_key": "cancel-before-resume",
                "command_type": "CANCEL",
                "payload": {},
            },
        )
        self.assertEqual(cancelled.status_code, 200)
        with self.assertRaisesRegex(AuthorityDenied, "MISSION_TERMINAL"):
            adapter.authorize_assignment(
                actor=self.owner,
                agent=self.agent,
                assignment_id=ASSIGNMENT_ID,
                mission_id=mission_id,
                correlation_id=CORRELATION,
            )
        with self.assertRaisesRegex(AuthorityDenied, "MISSION_TERMINAL"):
            adapter.authorize_resume(
                workload=self.worker,
                delegation_id=grant_id,
                agent_id=AGENT_ID,
                assignment_id=ASSIGNMENT_ID,
                mission_id=mission_id,
                binding_id=BINDING_ID,
                correlation_id=CORRELATION,
            )

    def test_terminal_mission_denies_scout_context_read(self):
        service = AquilaService(LegionKernel())
        mission_id = self.create_mission(service)
        adapter = InProcessAquilaAgentAuthority(service)
        grant_id = service.issue_delegation(
            issuer=self.owner,
            subject=self.worker,
            mission_id=mission_id,
            allowed_operations=frozenset({"READ_MISSION"}),
            roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )
        cancelled = service.submit_command(
            actor=self.owner,
            mission_id=mission_id,
            body={
                "expected_version": 1,
                "idempotency_key": "cancel-before-scout-context",
                "command_type": "CANCEL",
                "payload": {},
            },
        )
        self.assertEqual(cancelled.status_code, 200)

        with self.assertRaisesRegex(AuthorityDenied, "MISSION_TERMINAL"):
            adapter.authorize_and_read(
                workload=self.worker,
                delegation_id=grant_id,
                agent_id=AGENT_ID,
                assignment_id=ASSIGNMENT_ID,
                work_item_id="77777777-7777-4777-8777-777777777777",
                attempt_id="88888888-8888-4888-8888-888888888888",
                mission_id=mission_id,
                correlation_id=CORRELATION,
            )

        event = service.kernel.timeline(mission_id)[-1]
        self.assertEqual(
            event.event_type,
            "SCOUT_MISSION_CONTEXT_AUTHORIZATION_EVALUATED",
        )
        self.assertEqual(event.result, "DENY")
        self.assertEqual(event.data["reason"], "MISSION_TERMINAL")

    def test_grounded_knowledge_operations_get_fresh_decisions_and_safe_audit(self):
        service = AquilaService(LegionKernel())
        mission_id = self.create_mission(service)
        grant_id = service.issue_delegation(
            issuer=self.owner,
            subject=self.worker,
            mission_id=mission_id,
            allowed_operations=frozenset({"READ_KNOWLEDGE"}),
            roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )
        private_key = Ed25519PrivateKey.generate()
        sts = InMemorySecurityTokenService(
            Ed25519AssertionVerifier({"aquila-test": private_key.public_key()})
        )
        adapter = InProcessAquilaKnowledgeAuthority(
            service,
            lambda claims: sts.issue(
                sign_assertion(claims, private_key, key_id="aquila-test")
            ).token,
        )
        binding = ScopeBinding(BINDING_ID, "1.0.0")
        work_item_id = "77777777-7777-4777-8777-777777777777"
        attempt_id = "88888888-8888-4888-8888-888888888888"
        request = GroundedEvidenceReadRequest(
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_id=mission_id,
            agent_id=AGENT_ID,
            assignment_id=ASSIGNMENT_ID,
            workload=self.worker,
            delegation_id=grant_id,
            work_item_id=work_item_id,
            attempt_id=attempt_id,
            query="secret query must not enter audit",
            correlation_id=CORRELATION,
        )

        first = adapter.authorize_operation(request, binding)
        second = adapter.authorize_operation(request, binding)
        self.assertNotEqual(first.decision_id, second.decision_id)
        self.assertNotEqual(first.token, second.token)
        self.assertNotIn(first.token, repr(service.kernel.timeline(mission_id)))
        adapter.record_outcome(
            request,
            binding,
            invocation_id=second.invocation_id,
            result="SUCCESS",
            tabula_audit_correlation_id=(
                "99999999-9999-4999-8999-999999999999"
            ),
            record_references=(
                {
                    "record_id": "record-one",
                    "revision": "rev-1",
                    "canonical_uri": "tabula://corpus/record-one/rev-1",
                },
            ),
            successful_authorization_decision_id=second.decision_id,
        )
        events = service.kernel.timeline(mission_id)
        authorizations = [
            event
            for event in events
            if event.event_type == "EXTERNAL_READ_AUTHORIZATION_EVALUATED"
        ]
        self.assertEqual(len(authorizations), 2)
        self.assertNotEqual(
            authorizations[0].data["decision_id"],
            authorizations[1].data["decision_id"],
        )
        self.assertTrue(
            all(event.data["work_item_id"] == work_item_id for event in authorizations)
        )
        outcome = events[-1]
        self.assertEqual(outcome.data["attempt_id"], attempt_id)
        self.assertEqual(
            outcome.data["successful_authorization_decision_id"],
            second.decision_id,
        )
        audit_text = repr(events) + repr(sts.audit_events)
        self.assertNotIn(request.query, audit_text)
        self.assertNotIn(first.token, audit_text)
        self.assertNotIn(second.token, audit_text)

        service.revoke_delegation(
            actor=self.owner,
            mission_id=mission_id,
            delegation_id=grant_id,
            reason="End knowledge access.",
        )
        with self.assertRaisesRegex(AuthorityDenied, "DELEGATION_REVOKED"):
            adapter.authorize_operation(request, binding)


if __name__ == "__main__":
    unittest.main()
