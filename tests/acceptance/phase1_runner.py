"""Behavioral evidence runner for the first persistent Centurion."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
import tempfile
from typing import Callable

from aquila_api import InProcessAquilaAgentAuthority, PersistentAquilaService
from legion_kernel import Principal, PrincipalType, RoeLevel
from legion_runtime import (
    AssignmentStatus,
    AuthorityUnavailable,
    BindingStatus,
    MissionAuthorityView,
    PersistentAgentRuntime,
    RuntimeOperationError,
)
from tests.runtime_postgres import (
    new_runtime_store,
    reset_runtime_database,
    runtime_table_names,
)


CATALOG = Path(__file__).with_name("phase1-persistent-centurion.yaml")
CATALOG_IDS = tuple(re.findall(r"^  - id: (P1-\d+)$", CATALOG.read_text(), re.MULTILINE))
ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"


@dataclass
class ScenarioResult:
    scenario_id: str
    status: str
    evidence: dict[str, object] = field(default_factory=dict)
    assertions: list[dict[str, str]] = field(default_factory=list)
    failure: str | None = None


class ToggleAuthority:
    def __init__(self, mission_id: str) -> None:
        self.mission_id = mission_id
        self.unavailable = True

    def authorize_assignment(self, **kwargs):
        if self.unavailable:
            raise AuthorityUnavailable()
        return self._view()

    def authorize_resume(self, **kwargs):
        return self._view()

    def _view(self):
        return MissionAuthorityView(
            mission_id=self.mission_id,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            mission_status="ACTIVE",
            mission_version=1,
            roe_revision=1,
            decision_id="acceptance-decision",
            policy_version="acceptance-1",
            evaluated_at="2026-09-17T00:00:00Z",
        )


class Phase1AcceptanceRunner:
    def __init__(self) -> None:
        self.owner = Principal(
            PrincipalType.HUMAN,
            "phase1-owner",
            frozenset({"MISSION_OWNER", "OPERATOR"}),
        )
        self.observer = Principal(
            PrincipalType.HUMAN, "phase1-observer", frozenset({"OBSERVER"})
        )
        self._scenarios: dict[str, Callable[[], ScenarioResult]] = {
            "P1-001": self._p1_001,
            "P1-002": self._p1_002,
            "P1-003": self._p1_003,
            "P1-004": self._p1_004,
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

    def _mission(self, aquila: PersistentAquilaService) -> str:
        response = aquila.create_mission(
            actor=self.owner,
            body={
                "organization_id": ORG,
                "workspace_id": WORKSPACE,
                "title": "Phase 1 acceptance",
                "objective": "Prove one persistent Centurion.",
            },
        )
        assert response.status_code == 201
        return str(response.body["id"])

    def _agent_assignment(self, runtime, mission_id, actor=None):
        agent = runtime.create_centurion(
            actor=self.owner,
            organization_id=ORG,
            workspace_id=WORKSPACE,
            display_name="Primus",
            idempotency_key="create-primus",
        )
        assignment = runtime.request_assignment(
            actor=actor or self.owner,
            agent_id=agent.agent_id,
            mission_id=mission_id,
            correlation_id="33333333-3333-4333-8333-333333333333",
            idempotency_key="assign-primus",
        )
        return agent, assignment

    def _grant(self, aquila, mission_id, workload):
        return aquila.issue_delegation(
            issuer=self.owner,
            subject=workload,
            mission_id=mission_id,
            allowed_operations=frozenset({"READ_MISSION"}),
            roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )

    def _p1_001(self) -> ScenarioResult:
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            aquila_path = str(Path(directory) / "aquila.sqlite3")
            aquila = PersistentAquilaService(aquila_path)
            mission_id = self._mission(aquila)
            runtime = PersistentAgentRuntime(
                new_runtime_store(), InProcessAquilaAgentAuthority(aquila)
            )
            agent, assignment = self._agent_assignment(runtime, mission_id)
            workload_a = Principal(PrincipalType.WORKLOAD, "phase1-workload-a")
            first = runtime.resume_assignment(
                assignment_id=assignment.assignment_id,
                workload=workload_a,
                delegation_id=self._grant(aquila, mission_id, workload_a),
                correlation_id="44444444-4444-4444-8444-444444444444",
                idempotency_key="resume-a",
            )
            runtime.close()
            aquila.close()
            aquila = PersistentAquilaService(aquila_path)
            runtime = PersistentAgentRuntime(
                new_runtime_store(), InProcessAquilaAgentAuthority(aquila)
            )
            workload_b = Principal(PrincipalType.WORKLOAD, "phase1-workload-b")
            grant_b = self._grant(aquila, mission_id, workload_b)
            second = runtime.resume_assignment(
                assignment_id=assignment.assignment_id,
                workload=workload_b,
                delegation_id=grant_b,
                correlation_id="55555555-5555-4555-8555-555555555555",
                idempotency_key="resume-b",
            )
            event_count = len(runtime.list_events(agent.agent_id))
            replay = runtime.resume_assignment(
                assignment_id=assignment.assignment_id,
                workload=workload_b,
                delegation_id=grant_b,
                correlation_id="55555555-5555-4555-8555-555555555555",
                idempotency_key="resume-b",
            )
            bindings = runtime.list_bindings(assignment.assignment_id)
            assert second.agent.agent_id == agent.agent_id
            assert second.checkpoint.next_intent == first.checkpoint.next_intent
            assert [item.status for item in bindings] == [
                BindingStatus.RELEASED,
                BindingStatus.ACTIVE,
            ]
            assert replay.binding.binding_id == second.binding.binding_id
            assert len(runtime.list_events(agent.agent_id)) == event_count
            evidence = {
                "agent_id": agent.agent_id,
                "assignment_id": assignment.assignment_id,
                "checkpoint_intent": second.checkpoint.next_intent.value,
                "workload_bindings": [item.workload_subject for item in bindings],
                "runtime_event_count": event_count,
            }
            runtime.close()
            aquila.close()
            return self._pass("P1-001", evidence, "identity", "checkpoint", "binding", "replay")

    def _p1_002(self) -> ScenarioResult:
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            mission_id = "66666666-6666-4666-8666-666666666666"
            authority = ToggleAuthority(mission_id)
            runtime = PersistentAgentRuntime(new_runtime_store(), authority)
            agent, blocked = self._agent_assignment(runtime, mission_id)
            assert blocked.status == AssignmentStatus.BLOCKED
            try:
                runtime.resume_assignment(
                    assignment_id=blocked.assignment_id,
                    workload=Principal(PrincipalType.WORKLOAD, "phase1-workload"),
                    delegation_id="read-only-grant",
                    correlation_id="77777777-7777-4777-8777-777777777777",
                    idempotency_key="invalid-resume",
                )
            except RuntimeOperationError as exc:
                assert exc.code == "ASSIGNMENT_NOT_AUTHORIZED"
            else:
                raise AssertionError("resume bypassed assignment authority")
            runtime.close()
            runtime = PersistentAgentRuntime(new_runtime_store(), authority)
            authority.unavailable = False
            assigned = runtime.reconcile_assignment(
                assignment_id=blocked.assignment_id,
                actor=self.owner,
                idempotency_key="reconcile-primus",
            )
            assert assigned.status == AssignmentStatus.ASSIGNED
            evidence = {
                "agent_id": agent.agent_id,
                "blocked_error": blocked.last_error_code,
                "reconciled_status": assigned.status.value,
            }
            runtime.close()
            return self._pass("P1-002", evidence, "blocked", "no-bypass", "reconciled")

    def _p1_003(self) -> ScenarioResult:
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            aquila = PersistentAquilaService(str(Path(directory) / "aquila.sqlite3"))
            mission_id = self._mission(aquila)
            runtime = PersistentAgentRuntime(
                new_runtime_store(),
                InProcessAquilaAgentAuthority(aquila),
            )
            agent, assignment = self._agent_assignment(runtime, mission_id, self.observer)
            assert assignment.status == AssignmentStatus.REJECTED
            events = aquila.kernel.timeline(mission_id)
            denial = events[-1]
            assert denial.event_type == "AGENT_ASSIGNMENT_AUTHORIZATION_EVALUATED"
            assert denial.result == "DENY"
            assert aquila.kernel.get_mission(mission_id).version == 1
            evidence = {
                "agent_id": agent.agent_id,
                "assignment_status": assignment.status.value,
                "denial_reason": assignment.last_error_code,
                "mission_version": 1,
            }
            runtime.close()
            aquila.close()
            return self._pass("P1-003", evidence, "denied", "audited", "unchanged")

    def _p1_004(self) -> ScenarioResult:
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            aquila = PersistentAquilaService(str(Path(directory) / "aquila.sqlite3"))
            mission_id = self._mission(aquila)
            runtime = PersistentAgentRuntime(
                new_runtime_store(),
                InProcessAquilaAgentAuthority(aquila),
            )
            agent, assignment = self._agent_assignment(runtime, mission_id)
            aquila_tables = {
                row[0]
                for row in aquila.store.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            runtime_tables = runtime_table_names(runtime.repository)
            assert "agents" not in aquila_tables
            assert "missions" not in runtime_tables
            assert {"agents", "mission_assignments", "coordination_checkpoints"} <= runtime_tables
            evidence = {
                "agent_id": agent.agent_id,
                "assignment_id": assignment.assignment_id,
                "aquila_has_agents": "agents" in aquila_tables,
                "runtime_has_missions": "missions" in runtime_tables,
            }
            runtime.close()
            aquila.close()
            return self._pass("P1-004", evidence, "runtime-owner", "aquila-owner", "separate")


def main() -> int:
    results = Phase1AcceptanceRunner().run_all()
    print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    return 0 if all(result.status == "PASS" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
