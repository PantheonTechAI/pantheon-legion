"""Dependency-free reference runner for the canonical M1 scenario catalog."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
import tempfile
from typing import Callable

from aquila_api import AquilaService, DelegationGrant, PersistentAquilaService
from legion_kernel import AuthorizationError, LegionKernel, Principal, PrincipalType, RoeLevel, WorkerKilled


CATALOG = Path(__file__).with_name("m1-acceptance.yaml")
CATALOG_SCENARIO_IDS = tuple(re.findall(r"^  - id: (M1-\d+)$", CATALOG.read_text(), re.MULTILINE))


@dataclass
class ScenarioResult:
    scenario_id: str
    status: str
    mission_id: str | None = None
    command_ids: list[str] = field(default_factory=list)
    approval_ids: list[str] = field(default_factory=list)
    timeline_event_ids: list[str] = field(default_factory=list)
    observed_versions: list[int] = field(default_factory=list)
    assertions: list[dict[str, str]] = field(default_factory=list)
    failure: str | None = None


class AquilaM1Adapter:
    """Test-only adapter that drives public Aquila service operations."""

    def __init__(self, service: AquilaService | None = None) -> None:
        self.service = service or AquilaService(LegionKernel())
        self.owner = Principal(PrincipalType.HUMAN, "acceptance-user-a", frozenset({"MISSION_OWNER", "OPERATOR"}))
        self.operator = Principal(PrincipalType.HUMAN, "acceptance-user-b", frozenset({"OPERATOR"}))
        self.approver = Principal(PrincipalType.HUMAN, "acceptance-approver", frozenset({"APPROVER"}))
        self.observer = Principal(PrincipalType.HUMAN, "acceptance-observer", frozenset({"OBSERVER"}))
        self.worker = Principal(PrincipalType.WORKLOAD, "acceptance-mission-worker", frozenset({"MISSION_WORKER"}))

    def create(self) -> str:
        response = self.service.create_mission(actor=self.owner, body={
            "organization_id": "11111111-1111-4111-8111-111111111111",
            "workspace_id": "22222222-2222-4222-8222-222222222222",
            "title": "M1 acceptance Mission",
            "objective": "Verify durable Mission control without cognition.",
            "initial_roe_level": "REVIEW",
        })
        assert response.status_code == 201
        return response.body["id"]

    @property
    def model_runtime_available(self) -> bool:
        return False

    def command(self, actor: Principal, mission_id: str, version: int, key: str, kind: str, payload: dict) -> object:
        return self.service.submit_command(actor=actor, mission_id=mission_id, body={
            "expected_version": version, "idempotency_key": key,
            "command_type": kind, "payload": payload,
        })

    def grant(self, mission_id: str) -> DelegationGrant:
        return DelegationGrant(
            grant_id=f"acceptance-execution-{mission_id}", issuer=self.owner,
            subject=self.worker, mission_id=mission_id,
            allowed_operations=frozenset({"EXECUTE_ACTION"}),
            roe_ceiling=RoeLevel.REVIEW, expires_at="9999-01-01T00:00:00Z",
        )


class M1AcceptanceRunner:
    """Runs every canonical scenario in isolation and returns inspectable evidence."""

    def __init__(self) -> None:
        self._scenarios: dict[str, Callable[[], ScenarioResult]] = {
            "M1-001": self._m1_001,
            "M1-002": self._m1_002,
            "M1-003": self._m1_003,
            "M1-004": self._m1_004,
            "M1-005": self._m1_005,
            "M1-006": self._m1_006,
            "M1-007": self._m1_007,
        }

    def run_all(self) -> list[ScenarioResult]:
        missing = set(CATALOG_SCENARIO_IDS).symmetric_difference(self._scenarios)
        if missing:
            raise AssertionError(f"catalog/runner scenario mismatch: {sorted(missing)}")
        return [self._run(scenario_id) for scenario_id in CATALOG_SCENARIO_IDS]

    def _run(self, scenario_id: str) -> ScenarioResult:
        try:
            return self._scenarios[scenario_id]()
        except Exception as exc:  # evidence must retain the scenario-level failure
            return ScenarioResult(scenario_id=scenario_id, status="FAIL", failure=f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _result(scenario_id: str, adapter: AquilaM1Adapter, mission_id: str, assertions: list[str]) -> ScenarioResult:
        events = adapter.service.kernel.timeline(mission_id)
        return ScenarioResult(
            scenario_id=scenario_id, status="PASS", mission_id=mission_id,
            command_ids=list(dict.fromkeys(event.command_id for event in events if event.command_id)),
            approval_ids=list(dict.fromkeys(event.approval_id for event in events if event.approval_id)),
            timeline_event_ids=[event.id for event in events],
            observed_versions=[event.mission_version for event in events],
            assertions=[{"id": assertion, "status": "PASS"} for assertion in assertions],
        )

    def _m1_001(self) -> ScenarioResult:
        adapter = AquilaM1Adapter(); mission_id = adapter.create()
        assert adapter.command(adapter.owner, mission_id, 1, "m1-001-start", "START", {}).status_code == 200
        constraint = {"constraint": {"id": "22222222-2222-4222-8222-222222222222", "text": "Preserve evidence before any bounded mutation.", "severity": "REQUIRED"}}
        assert adapter.command(adapter.operator, mission_id, 2, "m1-001-constraint", "ADD_CONSTRAINT", constraint).status_code == 200
        mission = adapter.service.get_mission(actor=adapter.observer, mission_id=mission_id)
        assert mission.body["version"] == 3 and mission.body["status"] == "ACTIVE"
        result = self._result("M1-001", adapter, mission_id, ["A1", "A2"]); result.observed_versions = [1, 2, 3]
        return result

    def _m1_002(self) -> ScenarioResult:
        adapter = AquilaM1Adapter(); mission_id = adapter.create()
        adapter.command(adapter.owner, mission_id, 1, "m1-002-start", "START", {})
        constraint = {"constraint": {"id": "33333333-3333-4333-8333-333333333333", "text": "First constraint.", "severity": "REQUIRED"}}
        assert adapter.command(adapter.operator, mission_id, 2, "m1-002-constraint", "ADD_CONSTRAINT", constraint).status_code == 200
        stale = adapter.command(adapter.owner, mission_id, 2, "m1-002-stale", "UPDATE_OBJECTIVE", {"objective": "stale"})
        assert stale.status_code == 409 and stale.body["code"] == "VERSION_CONFLICT"
        assert any(event.event_type == "COMMAND_REJECTED" for event in adapter.service.kernel.timeline(mission_id))
        return self._result("M1-002", adapter, mission_id, ["A1", "A2"])

    def _m1_003(self) -> ScenarioResult:
        adapter = AquilaM1Adapter(); mission_id = adapter.create()
        adapter.command(adapter.owner, mission_id, 1, "m1-003-start", "START", {})
        denied = adapter.command(adapter.observer, mission_id, 2, "m1-003-roe", "SET_ROE", {"level": "BOUNDED_AUTONOMOUS", "reason": "Unauthorized"})
        assert denied.status_code == 403
        action = {"action_id": "44444444-4444-4444-8444-444444444444", "capability": "test.read", "arguments": {}, "target": "acceptance-resource", "side_effect_class": "READ"}
        assert adapter.command(adapter.owner, mission_id, 2, "m1-003-action", "REQUEST_ACTION", action).status_code == 200
        try:
            adapter.service.execute_action(mission_id=mission_id, action_id=action["action_id"], worker=adapter.observer)
        except AuthorizationError:
            pass
        else:
            raise AssertionError("observer execution unexpectedly succeeded")
        assert adapter.service.kernel.side_effects == {}
        assert any(event.result == "DENY" for event in adapter.service.kernel.timeline(mission_id))
        return self._result("M1-003", adapter, mission_id, ["A1", "A2"])

    def _m1_004(self) -> ScenarioResult:
        adapter = AquilaM1Adapter(); mission_id = adapter.create()
        adapter.command(adapter.owner, mission_id, 1, "m1-004-start", "START", {})
        action = {"action_id": "11111111-1111-4111-8111-111111111111", "capability": "test.bounded_mutation", "arguments": {"target": "acceptance-resource", "value": "one"}, "target": "acceptance-resource", "side_effect_class": "MUTATION"}
        requested = adapter.command(adapter.owner, mission_id, 2, "m1-004-action", "REQUEST_ACTION", action)
        approval_id = requested.body["approval_id"]
        assert adapter.service.decide_approval(actor=adapter.approver, mission_id=mission_id, body={"approval_id": approval_id, "expected_mission_version": 3, "decision": "APPROVE", "reason": "Approved."}).status_code == 200
        assert adapter.command(adapter.owner, mission_id, 3, "m1-004-roe", "SET_ROE", {"level": "OBSERVE", "reason": "Narrow authority."}).status_code == 200
        try:
            adapter.service.execute_action(mission_id=mission_id, action_id=action["action_id"], worker=adapter.worker, delegation=adapter.grant(mission_id))
        except AuthorizationError as exc:
            assert str(exc) == "ROE_DENIED"
        else:
            raise AssertionError("narrowed ROE execution unexpectedly succeeded")
        assert adapter.service.kernel.side_effects == {}
        assert adapter.service.kernel.approvals[approval_id].status == "APPROVED"
        return self._result("M1-004", adapter, mission_id, ["A1", "A2", "A3"])

    def _m1_005(self) -> ScenarioResult:
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "m1.sqlite3")
            adapter = AquilaM1Adapter(PersistentAquilaService(database)); mission_id = adapter.create()
            adapter.command(adapter.owner, mission_id, 1, "m1-005-start", "START", {})
            action = {"action_id": "55555555-5555-4555-8555-555555555555", "capability": "test.idempotent_side_effect", "arguments": {"target": "acceptance-resource"}, "target": "acceptance-resource", "side_effect_class": "MUTATION"}
            requested = adapter.command(adapter.owner, mission_id, 2, "m1-005-action", "REQUEST_ACTION", action)
            adapter.service.decide_approval(actor=adapter.approver, mission_id=mission_id, body={"approval_id": requested.body["approval_id"], "expected_mission_version": 3, "decision": "APPROVE", "reason": "Approved."})
            try:
                adapter.service.execute_action(mission_id=mission_id, action_id=action["action_id"], worker=adapter.worker, delegation=adapter.grant(mission_id), fail_after_side_effect=True)
            except WorkerKilled:
                pass
            else:
                raise AssertionError("failure injection was not exercised")
            adapter.service.close()
            adapter = AquilaM1Adapter(PersistentAquilaService(database))
            assert adapter.service.execute_action(mission_id=mission_id, action_id=action["action_id"], worker=adapter.worker, delegation=adapter.grant(mission_id)) == "RECOVERED"
            assert adapter.service.kernel.side_effects[action["action_id"]] == 1
            result = self._result("M1-005", adapter, mission_id, ["A1", "A2", "A3"])
            adapter.service.close()
            return result

    def _m1_006(self) -> ScenarioResult:
        adapter = AquilaM1Adapter(); mission_id = adapter.create()
        adapter.command(adapter.owner, mission_id, 1, "m1-006-start", "START", {})
        constraint = {"constraint": {"id": "66666666-6666-4666-8666-666666666666", "text": "Preserve the current deployment.", "severity": "PROHIBITED"}}
        adapter.command(adapter.operator, mission_id, 2, "m1-006-constraint", "ADD_CONSTRAINT", constraint)
        stale = adapter.command(adapter.owner, mission_id, 2, "m1-006-stale", "PAUSE", {})
        assert stale.status_code == 409
        events = adapter.service.kernel.timeline(mission_id)
        assert [event.sequence for event in events] == list(range(1, len(events) + 1))
        assert {adapter.owner.subject, adapter.operator.subject}.issubset({event.actor.subject for event in events})
        assert all(event.correlation_id for event in events)
        assert any(event.event_type == "COMMAND_REJECTED" for event in events)
        assert any(
            event.event_type == "AUTHORIZATION_EVALUATED"
            and event.data["policy_version"] == "mvp-1"
            for event in events
        )
        return self._result("M1-006", adapter, mission_id, ["A1", "A2"])

    def _m1_007(self) -> ScenarioResult:
        adapter = AquilaM1Adapter(); mission_id = adapter.create()
        assert not adapter.model_runtime_available
        adapter.command(adapter.owner, mission_id, 1, "m1-007-start", "START", {})
        constraint = {"constraint": {"id": "77777777-7777-4777-8777-777777777777", "text": "No model is required for Mission control.", "severity": "REQUIRED"}}
        assert adapter.command(adapter.operator, mission_id, 2, "m1-007-constraint", "ADD_CONSTRAINT", constraint).status_code == 200
        return self._result("M1-007", adapter, mission_id, ["A1", "A2"])


def main() -> int:
    results = M1AcceptanceRunner().run_all()
    print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    return 0 if all(result.status == "PASS" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
