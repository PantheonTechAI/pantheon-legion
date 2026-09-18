"""Seed or verify delegated Scout state across a PostgreSQL restart."""

from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from legion_kernel import Principal, PrincipalType
from legion_runtime import (
    AgentCognitionResult,
    AuthorizedMissionContext,
    MissionAuthorityView,
    PersistentAgentRuntime,
    WorkStatus,
)
from legion_runtime.database import runtime_work_items
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
MISSION = "33333333-3333-4333-8333-333333333333"
CORRELATION = "44444444-4444-4444-8444-444444444444"
OBJECTIVE = "Phase 2 restart probe"


class RestartPorts:
    def _view(self):
        return MissionAuthorityView(
            mission_id=MISSION,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_status="ACTIVE",
            mission_version=1,
            roe_revision=1,
            decision_id="restart-agent-decision",
            policy_version="restart-1",
            evaluated_at="2026-09-18T00:00:00Z",
        )

    def authorize_assignment(self, **kwargs):
        return self._view()

    def authorize_resume(self, **kwargs):
        return self._view()

    def authorize_and_read(self, **kwargs):
        return AuthorizedMissionContext(
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_id=MISSION,
            mission_version=2,
            mission_status="ACTIVE",
            title="Restart proof",
            objective=OBJECTIVE,
            roe_level="OBSERVE",
            constraints=("Read only",),
            authorization_decision_id="restart-context-decision",
            policy_version="restart-2",
            roe_revision=1,
            evaluated_at="2026-09-18T00:01:00Z",
        )

    def run(self, request):
        return AgentCognitionResult(
            request_id=request.request_id,
            agent_id=request.agent_id,
            work_item_id=request.work_item_id,
            attempt_id=request.attempt_id,
            mission_id=request.mission_id,
            mission_version=request.mission_version,
            summary="Restart-persistent Scout result",
            evidence_references=("restart:evidence",),
        )


def _runtime():
    ports = RestartPorts()
    return PersistentAgentRuntime(
        new_runtime_store(), ports, mission_context=ports, cognition=ports
    )


def seed() -> dict[str, object]:
    reset_runtime_database()
    runtime = _runtime()
    owner = Principal(
        PrincipalType.HUMAN,
        "restart-owner",
        frozenset({"MISSION_OWNER", "OPERATOR"}),
    )
    centurion = runtime.create_centurion(
        actor=owner,
        organization_id=ORG,
        workspace_id=WORKSPACE,
        display_name="Restart Centurion",
        idempotency_key="create-centurion",
    )
    scout = runtime.create_scout(
        actor=owner,
        organization_id=ORG,
        workspace_id=WORKSPACE,
        display_name="Restart Scout",
        idempotency_key="create-scout",
    )
    centurion_assignment = runtime.request_assignment(
        actor=owner,
        agent_id=centurion.agent_id,
        mission_id=MISSION,
        correlation_id=CORRELATION,
        idempotency_key="assign-centurion",
    )
    scout_assignment = runtime.request_assignment(
        actor=owner,
        agent_id=scout.agent_id,
        mission_id=MISSION,
        correlation_id=CORRELATION,
        idempotency_key="assign-scout",
    )
    centurion_workload = Principal(PrincipalType.WORKLOAD, "restart-centurion")
    scout_workload = Principal(PrincipalType.WORKLOAD, "restart-scout")
    centurion_binding = runtime.resume_assignment(
        assignment_id=centurion_assignment.assignment_id,
        workload=centurion_workload,
        delegation_id="restart-centurion-grant",
        correlation_id=CORRELATION,
        idempotency_key="resume-centurion",
    ).binding
    scout_binding = runtime.resume_assignment(
        assignment_id=scout_assignment.assignment_id,
        workload=scout_workload,
        delegation_id="restart-scout-grant",
        correlation_id=CORRELATION,
        idempotency_key="resume-scout",
    ).binding
    work = runtime.delegate_work(
        centurion_binding_id=centurion_binding.binding_id,
        workload=centurion_workload,
        scout_assignment_id=scout_assignment.assignment_id,
        objective=OBJECTIVE,
        required_capabilities=("read_only_analysis",),
        correlation_id=CORRELATION,
        idempotency_key="delegate",
    )
    attempt = runtime.claim_work(
        work_item_id=work.work_item_id,
        scout_binding_id=scout_binding.binding_id,
        workload=scout_workload,
        idempotency_key="claim",
    )
    result = runtime.execute_scout_work(
        work_item_id=work.work_item_id,
        scout_binding_id=scout_binding.binding_id,
        workload=scout_workload,
        idempotency_key="execute",
    )
    evidence = {
        "centurion_agent_id": centurion.agent_id,
        "scout_agent_id": scout.agent_id,
        "work_item_id": work.work_item_id,
        "attempt_id": attempt.attempt_id,
        "result_id": result.result_id,
    }
    runtime.close()
    return evidence


def verify() -> dict[str, object]:
    runtime = _runtime()
    with runtime.repository.engine.connect() as connection:
        row = connection.execute(
            select(runtime_work_items).where(
                runtime_work_items.c.objective == OBJECTIVE
            )
        ).mappings().one()
    work = runtime.get_work_item(row["work_item_id"])
    result = runtime.get_work_result(row["work_item_id"])
    attempts = runtime.repository.list_work_attempts(row["work_item_id"])
    assert work is not None and work.status == WorkStatus.COMPLETED
    assert result is not None
    assert len(attempts) == 1
    assert runtime.get_agent(work.centurion_agent_id) is not None
    assert runtime.get_agent(work.scout_agent_id) is not None
    assert runtime.get_checkpoint(work.centurion_assignment_id) is not None
    assert runtime.get_checkpoint(work.scout_assignment_id) is not None
    assert runtime.list_bindings(work.centurion_assignment_id)
    assert runtime.list_bindings(work.scout_assignment_id)
    evidence = {
        "centurion_agent_id": work.centurion_agent_id,
        "scout_agent_id": work.scout_agent_id,
        "work_item_id": work.work_item_id,
        "attempt_id": attempts[0].attempt_id,
        "result_id": result.result_id,
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
