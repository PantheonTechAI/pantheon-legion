"""Seed or verify grounded evidence state across a Runtime PostgreSQL restart."""

from __future__ import annotations

import argparse
import json

from legion_kernel import Principal, PrincipalType
from legion_runtime import PersistentAgentRuntime, WorkKind, WorkStatus
from tests.runtime_postgres import new_runtime_store, reset_runtime_database
from tests.test_grounded_scout import (
    Authority,
    CORRELATION,
    EvidenceReader,
    GroundedCognition,
    MISSION,
    MissionContext,
    ORG,
    WORKSPACE,
)


OBJECTIVE = "Grounded PostgreSQL restart probe"


def _runtime():
    return PersistentAgentRuntime(
        new_runtime_store(),
        Authority(),
        mission_context=MissionContext(),
        cognition=GroundedCognition(),
        evidence_reader=EvidenceReader(),
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
    assignments = []
    bindings = []
    for role, agent in (("centurion", centurion), ("scout", scout)):
        assignment = runtime.request_assignment(
            actor=owner,
            agent_id=agent.agent_id,
            mission_id=MISSION,
            correlation_id=CORRELATION,
            idempotency_key=f"assign-{role}",
        )
        binding = runtime.resume_assignment(
            assignment_id=assignment.assignment_id,
            workload=Principal(PrincipalType.WORKLOAD, f"restart-{role}"),
            delegation_id=f"restart-{role}-grant",
            correlation_id=CORRELATION,
            idempotency_key=f"resume-{role}",
        ).binding
        assignments.append(assignment)
        bindings.append(binding)
    work = runtime.delegate_work(
        centurion_binding_id=bindings[0].binding_id,
        workload=Principal(PrincipalType.WORKLOAD, "restart-centurion"),
        scout_assignment_id=assignments[1].assignment_id,
        objective=OBJECTIVE,
        required_capabilities=("read_only_analysis", "tabula_corpus_read"),
        correlation_id=CORRELATION,
        idempotency_key="delegate-grounded",
        work_kind=WorkKind.GROUNDED_CORPUS_ANALYSIS,
    )
    attempt = runtime.claim_work(
        work_item_id=work.work_item_id,
        scout_binding_id=bindings[1].binding_id,
        workload=Principal(PrincipalType.WORKLOAD, "restart-scout"),
        idempotency_key="claim-grounded",
    )
    result = runtime.execute_scout_work(
        work_item_id=work.work_item_id,
        scout_binding_id=bindings[1].binding_id,
        workload=Principal(PrincipalType.WORKLOAD, "restart-scout"),
        idempotency_key="execute-grounded",
    )
    evidence = {
        "work_item_id": work.work_item_id,
        "attempt_id": attempt.attempt_id,
        "result_id": result.result_id,
        "evidence_reference_ids": list(result.evidence_references),
    }
    runtime.close()
    return evidence


def verify() -> dict[str, object]:
    runtime = _runtime()
    work = next(
        item for item in runtime.list_work_for_mission(MISSION) if item.objective == OBJECTIVE
    )
    result = runtime.get_work_result(work.work_item_id)
    references = runtime.list_work_evidence_references(work_item_id=work.work_item_id)
    assert work.status == WorkStatus.COMPLETED
    assert result is not None
    assert set(result.evidence_references) == {
        item.evidence_reference_id for item in references
    }
    evidence = {
        "work_item_id": work.work_item_id,
        "result_id": result.result_id,
        "evidence_reference_ids": list(result.evidence_references),
        "status": "GROUNDED_STATE_PERSISTED_AFTER_DATABASE_RESTART",
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
