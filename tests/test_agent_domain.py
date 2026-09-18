import unittest
from dataclasses import fields

from legion_runtime import (
    ActorRef,
    AgentIdentity,
    AgentRole,
    AgentRuntimeBinding,
    AgentStatus,
    AssignmentStatus,
    BindingStatus,
    CheckpointState,
    CoordinationCheckpoint,
    MissionAssignment,
    NextIntent,
    RuntimeEvent,
)


class AgentDomainTests(unittest.TestCase):
    def test_agent_identity_is_organizational_not_a_runtime_or_model(self):
        identity_fields = {field.name for field in fields(AgentIdentity)}
        self.assertEqual(
            identity_fields,
            {
                "agent_id",
                "organization_id",
                "workspace_id",
                "display_name",
                "role",
                "status",
                "version",
                "created_by",
                "created_at",
                "updated_at",
            },
        )
        forbidden = {
            "model",
            "prompt",
            "process",
            "container",
            "machine",
            "runtime",
            "credential",
            "token",
            "grant",
        }
        self.assertTrue(identity_fields.isdisjoint(forbidden))

    def test_agent_identity_validates_stable_scope(self):
        with self.assertRaisesRegex(ValueError, "organization_id"):
            AgentIdentity(
                agent_id="11111111-1111-4111-8111-111111111111",
                organization_id="not-a-uuid",
                workspace_id="22222222-2222-4222-8222-222222222222",
                display_name="First Centurion",
                role=AgentRole.CENTURION,
                status=AgentStatus.ACTIVE,
                version=1,
                created_by=ActorRef("HUMAN", "owner"),
                created_at="2026-09-17T00:00:00Z",
                updated_at="2026-09-17T00:00:00Z",
            )

    def test_assignment_checkpoint_and_binding_validate_revisions_and_subject(self):
        actor = ActorRef("HUMAN", "owner")
        with self.assertRaisesRegex(ValueError, "version"):
            MissionAssignment(
                assignment_id="11111111-1111-4111-8111-111111111111",
                agent_id="22222222-2222-4222-8222-222222222222",
                mission_id="33333333-3333-4333-8333-333333333333",
                status=AssignmentStatus.PENDING_AUTHORIZATION,
                mission_version=None,
                authorization_decision_id=None,
                policy_version=None,
                requested_by=actor,
                correlation_id="44444444-4444-4444-8444-444444444444",
                last_error_code=None,
                version=0,
                created_at="2026-09-17T00:00:00Z",
                updated_at="2026-09-17T00:00:00Z",
            )
        with self.assertRaisesRegex(ValueError, "revision"):
            CoordinationCheckpoint(
                assignment_id="11111111-1111-4111-8111-111111111111",
                revision=0,
                state=CheckpointState.READY,
                next_intent=NextIntent.ASSESS_MISSION,
                last_observed_mission_version=1,
                correlation_id="44444444-4444-4444-8444-444444444444",
                last_error_code=None,
                updated_at="2026-09-17T00:00:00Z",
            )
        with self.assertRaisesRegex(ValueError, "workload_subject"):
            AgentRuntimeBinding(
                binding_id="55555555-5555-4555-8555-555555555555",
                agent_id="22222222-2222-4222-8222-222222222222",
                assignment_id="11111111-1111-4111-8111-111111111111",
                workload_subject=" ",
                grant_id=None,
                status=BindingStatus.PENDING_AUTHORITY,
                version=1,
                started_at="2026-09-17T00:00:00Z",
                ended_at=None,
                correlation_id="44444444-4444-4444-8444-444444444444",
                last_error_code=None,
            )

    def test_runtime_event_metadata_is_serializable_and_bounded(self):
        values = {
            "event_id": "11111111-1111-4111-8111-111111111111",
            "sequence": 1,
            "event_type": "AgentCreated",
            "occurred_at": "2026-09-17T00:00:00Z",
            "agent_id": "22222222-2222-4222-8222-222222222222",
            "actor": ActorRef("HUMAN", "owner"),
            "result": "SUCCESS",
            "correlation_id": "44444444-4444-4444-8444-444444444444",
        }
        with self.assertRaisesRegex(TypeError, "JSON serializable"):
            RuntimeEvent(**values, data={"invalid": object()})
        with self.assertRaisesRegex(ValueError, "8192"):
            RuntimeEvent(**values, data={"oversized": "x" * 8192})


if __name__ == "__main__":
    unittest.main()
