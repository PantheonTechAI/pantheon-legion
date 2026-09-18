"""Behavioral evidence runner for the first durable delegated Scout cycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
import tempfile
from typing import Callable

from aquila_api import InProcessAquilaAgentAuthority, PersistentAquilaService
from legion_cognition import InMemoryScoutRuntime, LegacyScoutRuntimeBridge
from legion_kernel import Principal, PrincipalType, RoeLevel
from legion_runtime import (
    NextIntent,
    PersistentAgentRuntime,
    RuntimeOperationError,
    WorkStatus,
)
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


CATALOG = Path(__file__).with_name("phase2-first-delegated-scout.yaml")
CATALOG_IDS = tuple(re.findall(r"^  - id: (P2-\d+)$", CATALOG.read_text(), re.MULTILINE))
ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
CORRELATION = "33333333-3333-4333-8333-333333333333"


@dataclass
class ScenarioResult:
    scenario_id: str
    status: str
    evidence: dict[str, object] = field(default_factory=dict)
    assertions: list[dict[str, str]] = field(default_factory=list)
    failure: str | None = None


class CountingCognition:
    def __init__(self, delegate):
        self.delegate = delegate
        self.calls = 0

    def run(self, request):
        self.calls += 1
        return self.delegate.run(request)


class Phase2AcceptanceRunner:
    def __init__(self) -> None:
        self.owner = Principal(
            PrincipalType.HUMAN,
            "phase2-owner",
            frozenset({"MISSION_OWNER", "OPERATOR"}),
        )
        self._scenarios: dict[str, Callable[[], ScenarioResult]] = {
            "P2-001": self._p2_001,
            "P2-002": self._p2_002,
            "P2-003": self._p2_003,
        }

    def run_all(self) -> list[ScenarioResult]:
        mismatch = set(CATALOG_IDS).symmetric_difference(self._scenarios)
        if mismatch:
            raise AssertionError(f"catalog/runner scenario mismatch: {sorted(mismatch)}")
        return [self._run(scenario_id) for scenario_id in CATALOG_IDS]

    def _run(self, scenario_id: str) -> ScenarioResult:
        try:
            return self._scenarios[scenario_id]()
        except Exception as exc:
            return ScenarioResult(
                scenario_id,
                "FAIL",
                failure=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _pass(scenario_id: str, evidence: dict[str, object], *assertions: str):
        return ScenarioResult(
            scenario_id,
            "PASS",
            evidence=evidence,
            assertions=[{"id": value, "status": "PASS"} for value in assertions],
        )

    def _composition(self, directory: str):
        aquila = PersistentAquilaService(str(Path(directory) / "aquila.sqlite3"))
        response = aquila.create_mission(
            actor=self.owner,
            body={
                "organization_id": ORG,
                "workspace_id": WORKSPACE,
                "title": "Phase 2 acceptance",
                "objective": "Prove one durable delegated Scout cycle.",
            },
        )
        mission_id = str(response.body["id"])
        adapter = InProcessAquilaAgentAuthority(aquila)
        cognition = CountingCognition(
            LegacyScoutRuntimeBridge(InMemoryScoutRuntime())
        )
        runtime = PersistentAgentRuntime(
            new_runtime_store(),
            adapter,
            mission_context=adapter,
            cognition=cognition,
        )
        centurion = runtime.create_centurion(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="Primus",
            idempotency_key="create-centurion",
        )
        scout = runtime.create_scout(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="Scout",
            idempotency_key="create-scout",
        )
        centurion_assignment = runtime.request_assignment(
            actor=self.owner,
            agent_id=centurion.agent_id,
            mission_id=mission_id,
            correlation_id=CORRELATION,
            idempotency_key="assign-centurion",
        )
        scout_assignment = runtime.request_assignment(
            actor=self.owner,
            agent_id=scout.agent_id,
            mission_id=mission_id,
            correlation_id=CORRELATION,
            idempotency_key="assign-scout",
        )
        centurion_workload = Principal(PrincipalType.WORKLOAD, "centurion-workload")
        scout_workload = Principal(PrincipalType.WORKLOAD, "scout-workload-a")
        centurion_binding = runtime.resume_assignment(
            assignment_id=centurion_assignment.assignment_id,
            workload=centurion_workload,
            delegation_id=self._grant(aquila, mission_id, centurion_workload),
            correlation_id=CORRELATION,
            idempotency_key="resume-centurion",
        ).binding
        scout_grant = self._grant(aquila, mission_id, scout_workload)
        scout_binding = runtime.resume_assignment(
            assignment_id=scout_assignment.assignment_id,
            workload=scout_workload,
            delegation_id=scout_grant,
            correlation_id=CORRELATION,
            idempotency_key="resume-scout-a",
        ).binding
        return {
            "aquila": aquila,
            "runtime": runtime,
            "cognition": cognition,
            "mission_id": mission_id,
            "centurion": centurion,
            "scout": scout,
            "centurion_assignment": centurion_assignment,
            "scout_assignment": scout_assignment,
            "centurion_binding": centurion_binding,
            "scout_binding": scout_binding,
            "centurion_workload": centurion_workload,
            "scout_workload": scout_workload,
            "scout_grant": scout_grant,
        }

    def _grant(self, aquila, mission_id, workload):
        return aquila.issue_delegation(
            issuer=self.owner,
            subject=workload,
            mission_id=mission_id,
            allowed_operations=frozenset({"READ_MISSION"}),
            roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )

    @staticmethod
    def _delegate(state):
        return state["runtime"].delegate_work(
            centurion_binding_id=state["centurion_binding"].binding_id,
            workload=state["centurion_workload"],
            scout_assignment_id=state["scout_assignment"].assignment_id,
            objective="Assess the bounded Mission context.",
            required_capabilities=("read_only_analysis",),
            correlation_id=CORRELATION,
            idempotency_key="delegate-one",
        )

    def _p2_001(self) -> ScenarioResult:
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            state = self._composition(directory)
            work = self._delegate(state)
            replacement_workload = Principal(
                PrincipalType.WORKLOAD, "scout-workload-b"
            )
            replacement = state["runtime"].resume_assignment(
                assignment_id=state["scout_assignment"].assignment_id,
                workload=replacement_workload,
                delegation_id=self._grant(
                    state["aquila"], state["mission_id"], replacement_workload
                ),
                correlation_id="44444444-4444-4444-8444-444444444444",
                idempotency_key="resume-scout-b",
            )
            assert replacement.checkpoint.next_intent == NextIntent.EXECUTE_WORK
            assert replacement.checkpoint.focus_work_item_id == work.work_item_id
            attempt = state["runtime"].claim_work(
                work_item_id=work.work_item_id,
                scout_binding_id=replacement.binding.binding_id,
                workload=replacement_workload,
                idempotency_key="claim-one",
            )
            result = state["runtime"].execute_scout_work(
                work_item_id=work.work_item_id,
                scout_binding_id=replacement.binding.binding_id,
                workload=replacement_workload,
                idempotency_key="execute-one",
            )
            state["runtime"].close()
            adapter = InProcessAquilaAgentAuthority(state["aquila"])
            runtime = PersistentAgentRuntime(
                new_runtime_store(), adapter, mission_context=adapter,
                cognition=state["cognition"],
            )
            assert runtime.get_work_item(work.work_item_id).status == WorkStatus.COMPLETED
            assert runtime.get_work_result(work.work_item_id).result_id == result.result_id
            evidence = {
                "centurion_agent_id": state["centurion"].agent_id,
                "scout_agent_id": state["scout"].agent_id,
                "work_item_id": work.work_item_id,
                "attempt_id": attempt.attempt_id,
                "result_id": result.result_id,
                "cognition_calls": state["cognition"].calls,
            }
            runtime.close()
            state["aquila"].close()
            return self._pass(
                "P2-001", evidence, "identity", "replacement", "authority", "result"
            )

    def _p2_002(self) -> ScenarioResult:
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            state = self._composition(directory)
            work = self._delegate(state)
            state["runtime"].claim_work(
                work_item_id=work.work_item_id,
                scout_binding_id=state["scout_binding"].binding_id,
                workload=state["scout_workload"],
                idempotency_key="claim-one",
            )
            state["aquila"].revoke_delegation(
                actor=self.owner,
                mission_id=state["mission_id"],
                delegation_id=state["scout_grant"],
                reason="Acceptance revocation.",
            )
            try:
                state["runtime"].execute_scout_work(
                    work_item_id=work.work_item_id,
                    scout_binding_id=state["scout_binding"].binding_id,
                    workload=state["scout_workload"],
                    idempotency_key="execute-one",
                )
            except RuntimeOperationError as exc:
                assert exc.code == "DELEGATION_REVOKED"
            else:
                raise AssertionError("revoked authority reached cognition")
            assert state["cognition"].calls == 0
            assert state["runtime"].get_work_result(work.work_item_id) is None
            evidence = {
                "work_item_id": work.work_item_id,
                "error_code": "DELEGATION_REVOKED",
                "cognition_calls": 0,
            }
            state["runtime"].close()
            state["aquila"].close()
            return self._pass("P2-002", evidence, "denied", "no-cognition", "no-result")

    def _p2_003(self) -> ScenarioResult:
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            state = self._composition(directory)
            work = self._delegate(state)
            cancelled = state["runtime"].cancel_work(
                work_item_id=work.work_item_id,
                centurion_binding_id=state["centurion_binding"].binding_id,
                workload=state["centurion_workload"],
                reason="Acceptance cancellation.",
                idempotency_key="cancel-one",
            )
            assert cancelled.status == WorkStatus.CANCELLED
            assert state["runtime"].get_work_result(work.work_item_id) is None
            centurion_events = state["runtime"].list_events(
                state["centurion"].agent_id
            )
            assert all(work.objective not in str(event.data) for event in centurion_events)
            evidence = {
                "work_item_id": work.work_item_id,
                "status": cancelled.status.value,
                "result_exists": False,
            }
            state["runtime"].close()
            state["aquila"].close()
            return self._pass("P2-003", evidence, "cancelled", "released", "references")


def main() -> int:
    results = Phase2AcceptanceRunner().run_all()
    print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    return 0 if all(result.status == "PASS" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
