"""Seed or verify persistent Centurion state across a PostgreSQL restart."""

from __future__ import annotations

import argparse
import json

from legion_kernel import Principal, PrincipalType
from legion_runtime import BindingStatus, MissionAuthorityView, PersistentAgentRuntime
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
MISSION = "33333333-3333-4333-8333-333333333333"
CORRELATION = "44444444-4444-4444-8444-444444444444"
AGENT = "00000000-0000-4000-8000-000000000001"
ASSIGNMENT = "00000000-0000-4000-8000-000000000004"
BINDING = "00000000-0000-4000-8000-000000000007"


class RestartAuthority:
    def _view(self) -> MissionAuthorityView:
        return MissionAuthorityView(
            mission_id=MISSION,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_status="ACTIVE",
            mission_version=1,
            roe_revision=1,
            decision_id="restart-evidence-decision",
            policy_version="restart-evidence-1",
            evaluated_at="2026-09-17T00:00:00Z",
        )

    def authorize_assignment(self, **kwargs) -> MissionAuthorityView:
        return self._view()

    def authorize_resume(self, **kwargs) -> MissionAuthorityView:
        return self._view()


def _id_factory():
    values = iter(
        f"00000000-0000-4000-8000-{value:012d}" for value in range(1, 20)
    )
    return lambda: next(values)


def seed() -> dict[str, object]:
    reset_runtime_database()
    runtime = PersistentAgentRuntime(
        new_runtime_store(), RestartAuthority(), id_factory=_id_factory()
    )
    owner = Principal(
        PrincipalType.HUMAN,
        "restart-owner",
        frozenset({"MISSION_OWNER", "OPERATOR"}),
    )
    agent = runtime.create_centurion(
        actor=owner,
        organization_id=ORG,
        workspace_id=WORKSPACE,
        display_name="Restart Primus",
        idempotency_key="restart-create",
    )
    assignment = runtime.request_assignment(
        actor=owner,
        agent_id=agent.agent_id,
        mission_id=MISSION,
        correlation_id=CORRELATION,
        idempotency_key="restart-assign",
    )
    resumed = runtime.resume_assignment(
        assignment_id=assignment.assignment_id,
        workload=Principal(PrincipalType.WORKLOAD, "restart-workload"),
        delegation_id="restart-grant",
        correlation_id="55555555-5555-4555-8555-555555555555",
        idempotency_key="restart-resume",
    )
    evidence = {
        "agent_id": agent.agent_id,
        "assignment_id": assignment.assignment_id,
        "binding_id": resumed.binding.binding_id,
        "checkpoint_revision": resumed.checkpoint.revision,
        "event_count": len(runtime.list_events(agent.agent_id)),
    }
    runtime.close()
    assert evidence["agent_id"] == AGENT
    assert evidence["assignment_id"] == ASSIGNMENT
    assert evidence["binding_id"] == BINDING
    return evidence


def verify() -> dict[str, object]:
    runtime = PersistentAgentRuntime(new_runtime_store(), RestartAuthority())
    agent = runtime.get_agent(AGENT)
    assignment = runtime.get_assignment(ASSIGNMENT)
    checkpoint = runtime.get_checkpoint(ASSIGNMENT)
    bindings = runtime.list_bindings(ASSIGNMENT)
    events = runtime.list_events(AGENT)
    assert agent is not None
    assert assignment is not None
    assert checkpoint is not None
    assert len(bindings) == 1
    assert bindings[0].binding_id == BINDING
    assert bindings[0].status == BindingStatus.ACTIVE
    assert len(events) == 5
    evidence = {
        "agent_id": agent.agent_id,
        "assignment_id": assignment.assignment_id,
        "binding_id": bindings[0].binding_id,
        "checkpoint_revision": checkpoint.revision,
        "event_count": len(events),
        "status": "PERSISTED_AFTER_DATABASE_RESTART",
    }
    runtime.close()
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "verify"))
    args = parser.parse_args()
    print(json.dumps(seed() if args.mode == "seed" else verify(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
