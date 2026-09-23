"""Behavioral evidence runner for grounded persistent Scout investigation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
from pathlib import Path
import re
import tempfile
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aquila_api import (
    InProcessAquilaAgentAuthority,
    InProcessAquilaKnowledgeAuthority,
    PersistentAquilaService,
)
from legion_cognition import InMemoryScoutRuntime, LegacyScoutRuntimeBridge
from legion_kernel import Principal, PrincipalType, RoeLevel
from legion_runtime import (
    AttemptStage,
    AttemptStatus,
    PersistentAgentRuntime,
    RepositoryMissionOrganizationReadModel,
    RuntimeOperationError,
    WorkKind,
    WorkStatus,
)
from legion_tabula import McpResponse, ScopeBinding, TabulaCorpusClient
from legion_tabula.runtime_adapter import FederatedCorpusEvidenceReader
from pantheon_sts import (
    Ed25519AssertionVerifier,
    InMemorySecurityTokenService,
    sign_assertion,
)
from tests.runtime_postgres import new_runtime_store, reset_runtime_database


CATALOG = Path(__file__).with_name("grounded-scout-investigation.yaml")
CATALOG_IDS = tuple(
    re.findall(r"^  - id: (GSI-\d+)$", CATALOG.read_text(), re.MULTILINE)
)
ORG = "11111111-1111-4111-8111-111111111111"
WORKSPACE = "22222222-2222-4222-8222-222222222222"
CORRELATION = "33333333-3333-4333-8333-333333333333"
BINDING = ScopeBinding("44444444-4444-4444-8444-444444444444", "1.0.0")
TABULA_AUDIT = "55555555-5555-4555-8555-555555555555"


@dataclass
class ScenarioResult:
    scenario_id: str
    status: str
    evidence: dict[str, object] = field(default_factory=dict)
    assertions: list[dict[str, str]] = field(default_factory=list)
    failure: str | None = None


class CountingCognition:
    def __init__(self) -> None:
        self.delegate = LegacyScoutRuntimeBridge(InMemoryScoutRuntime())
        self.calls = 0

    def run(self, request):
        self.calls += 1
        return self.delegate.run(request)


class FixtureTabulaTransport:
    """Exercise one-time token enforcement while returning contract-v1 evidence."""

    def __init__(self, sts: InMemorySecurityTokenService) -> None:
        self.sts = sts
        self.protected_calls = 0
        self.token_ids: list[str] = []

    def __call__(self, token, request):
        for _ in range(3):
            status = self.sts.introspect(token())
            assert status["active"] is True
            assert status["binding_id"] == BINDING.id
            self.protected_calls += 1
            self.token_ids.append(status["token_id"])
        arguments = request["arguments"]
        return McpResponse(
            200,
            {
                "schema_version": "1.0",
                "request_id": arguments["request_id"],
                "correlation_id": arguments["correlation_id"],
                "binding": arguments["binding"],
                "tabula_audit_correlation_id": TABULA_AUDIT,
                "results": [
                    {
                        "record_id": "acceptance-record",
                        "domain": "architecture",
                        "revision": "rev-1",
                        "canonical_uri": "tabula://corpus/acceptance-record/rev-1",
                        "source": {"citation": "non-durable citation"},
                        "recorded_at": "2026-09-18T00:00:00Z",
                        "retrieved_at": "2026-09-18T00:01:00Z",
                        "selection_explanation": "Matches the bounded objective.",
                        "content": "non-durable raw acceptance evidence",
                    }
                ],
            },
        )


class RevokingReader:
    def __init__(self, aquila, owner, mission_id, grant_id, delegate):
        self.aquila = aquila
        self.owner = owner
        self.mission_id = mission_id
        self.grant_id = grant_id
        self.delegate = delegate

    def read(self, request):
        self.aquila.revoke_delegation(
            actor=self.owner,
            mission_id=self.mission_id,
            delegation_id=self.grant_id,
            reason="Acceptance knowledge-boundary revocation.",
        )
        return self.delegate.read(request)


class GroundedScoutAcceptanceRunner:
    def __init__(self) -> None:
        self.owner = Principal(
            PrincipalType.HUMAN,
            "gsi-owner",
            frozenset({"MISSION_OWNER", "OPERATOR"}),
        )
        self._scenarios: dict[str, Callable[[], ScenarioResult]] = {
            "GSI-001": self._gsi_001,
            "GSI-002": self._gsi_002,
            "GSI-003": self._gsi_003,
            "GSI-004": self._gsi_004,
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

    def _composition(self, directory: str, *, mission_title="Grounded acceptance",
                     mission_objective="Prove authorized grounded persistent work."):
        aquila = PersistentAquilaService(str(Path(directory) / "aquila.sqlite3"))
        mission = aquila.create_mission(
            actor=self.owner,
            body={
                "organization_id": ORG,
                "workspace_id": WORKSPACE,
                "title": mission_title,
                "objective": mission_objective,
            },
        )
        mission_id = str(mission.body["id"])
        mission_authority = InProcessAquilaAgentAuthority(aquila)
        private_key = Ed25519PrivateKey.generate()
        sts = InMemorySecurityTokenService(
            Ed25519AssertionVerifier({"aquila-test": private_key.public_key()})
        )
        knowledge_authority = InProcessAquilaKnowledgeAuthority(
            aquila,
            lambda claims: sts.issue(
                sign_assertion(claims, private_key, key_id="aquila-test")
            ).token,
        )
        transport = FixtureTabulaTransport(sts)
        evidence_reader = FederatedCorpusEvidenceReader(
            client=TabulaCorpusClient(transport),
            authority=knowledge_authority,
            binding=BINDING,
        )
        cognition = CountingCognition()
        runtime = PersistentAgentRuntime(
            new_runtime_store(),
            mission_authority,
            mission_context=mission_authority,
            cognition=cognition,
            evidence_reader=evidence_reader,
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
            display_name="Grounded Scout",
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
        centurion_workload = Principal(PrincipalType.WORKLOAD, "gsi-centurion")
        scout_workload = Principal(PrincipalType.WORKLOAD, "gsi-scout")
        centurion_grant = self._grant(
            aquila, mission_id, centurion_workload, {"READ_MISSION"}
        )
        scout_grant = self._grant(
            aquila,
            mission_id,
            scout_workload,
            {"READ_MISSION", "READ_KNOWLEDGE"},
        )
        centurion_binding = runtime.resume_assignment(
            assignment_id=centurion_assignment.assignment_id,
            workload=centurion_workload,
            delegation_id=centurion_grant,
            correlation_id=CORRELATION,
            idempotency_key="resume-centurion",
        ).binding
        scout_binding = runtime.resume_assignment(
            assignment_id=scout_assignment.assignment_id,
            workload=scout_workload,
            delegation_id=scout_grant,
            correlation_id=CORRELATION,
            idempotency_key="resume-scout",
        ).binding
        return locals()

    def _grant(self, aquila, mission_id, workload, operations):
        return aquila.issue_delegation(
            issuer=self.owner,
            subject=workload,
            mission_id=mission_id,
            allowed_operations=frozenset(operations),
            roe_ceiling=RoeLevel.OBSERVE,
            expires_at="9999-01-01T00:00:00Z",
        )

    @staticmethod
    def _delegate(state, *, grounded=True, objective="Find grounded evidence."):
        return state["runtime"].delegate_work(
            centurion_binding_id=state["centurion_binding"].binding_id,
            workload=state["centurion_workload"],
            scout_assignment_id=state["scout_assignment"].assignment_id,
            objective=objective,
            required_capabilities=(
                ("read_only_analysis", "tabula_corpus_read")
                if grounded
                else ("read_only_analysis",)
            ),
            correlation_id=CORRELATION,
            idempotency_key="delegate-one",
            work_kind=(
                WorkKind.GROUNDED_CORPUS_ANALYSIS
                if grounded
                else WorkKind.READ_ONLY_ANALYSIS
            ),
        )

    @staticmethod
    def _claim_and_execute(state, work, suffix="one"):
        attempt = state["runtime"].claim_work(
            work_item_id=work.work_item_id,
            scout_binding_id=state["scout_binding"].binding_id,
            workload=state["scout_workload"],
            idempotency_key=f"claim-{suffix}",
        )
        result = state["runtime"].execute_scout_work(
            work_item_id=work.work_item_id,
            scout_binding_id=state["scout_binding"].binding_id,
            workload=state["scout_workload"],
            idempotency_key=f"execute-{suffix}",
        )
        return attempt, result

    @staticmethod
    def _close(state):
        state["runtime"].close()
        state["aquila"].close()

    def _gsi_001(self):
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            state = self._composition(directory)
            work = self._delegate(state)
            attempt, result = self._claim_and_execute(state, work)
            references = state["runtime"].list_work_evidence_references(
                work_item_id=work.work_item_id
            )
            safe_state = repr(references) + repr(
                state["runtime"].list_events(state["scout"].agent_id)
            )
            assert "non-durable raw acceptance evidence" not in safe_state
            state["runtime"].close()
            state["runtime"] = PersistentAgentRuntime(
                new_runtime_store(),
                state["mission_authority"],
                mission_context=state["mission_authority"],
                cognition=state["cognition"],
                evidence_reader=state["evidence_reader"],
            )
            snapshot = RepositoryMissionOrganizationReadModel(
                state["runtime"].repository
            ).snapshot(
                organization_id=ORG,
                workspace_id=WORKSPACE,
                mission_id=state["mission_id"],
            )
            assert state["runtime"].get_work_result(work.work_item_id).result_id == result.result_id
            assert len(snapshot.work[0].evidence) == 1
            evidence = {
                "mission_id": state["mission_id"],
                "centurion_agent_id": state["centurion"].agent_id,
                "scout_agent_id": state["scout"].agent_id,
                "work_item_id": work.work_item_id,
                "attempt_id": attempt.attempt_id,
                "result_id": result.result_id,
                "evidence_reference_ids": list(result.evidence_references),
                "protected_operation_count": state["transport"].protected_calls,
            }
            self._close(state)
            return self._pass(
                "GSI-001", evidence, "identity", "fresh-authority", "safe-provenance", "restart"
            )

    def _gsi_002(self):
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            state = self._composition(directory)
            state["runtime"].evidence_reader = RevokingReader(
                state["aquila"],
                self.owner,
                state["mission_id"],
                state["scout_grant"],
                state["evidence_reader"],
            )
            work = self._delegate(state)
            state["runtime"].claim_work(
                work_item_id=work.work_item_id,
                scout_binding_id=state["scout_binding"].binding_id,
                workload=state["scout_workload"],
                idempotency_key="claim-one",
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
                raise AssertionError("revoked knowledge authority reached cognition")
            assert state["cognition"].calls == 0
            assert state["transport"].protected_calls == 0
            assert state["runtime"].get_work_result(work.work_item_id) is None
            evidence = {
                "work_item_id": work.work_item_id,
                "error_code": "DELEGATION_REVOKED",
                "mission_context_authorized": True,
                "protected_operation_count": 0,
                "cognition_calls": 0,
            }
            self._close(state)
            return self._pass(
                "GSI-002", evidence, "mission-context", "knowledge-denied", "no-cognition"
            )

    def _gsi_003(self):
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            state = self._composition(directory)
            try:
                self._delegate(state, objective="x" * 2001)
            except RuntimeOperationError as exc:
                assert exc.code == "GROUNDED_OBJECTIVE_TOO_LONG"
            else:
                raise AssertionError("over-limit grounded objective persisted")
            assert not state["runtime"].list_work_for_assignment(
                state["scout_assignment"].assignment_id
            )
            work = self._delegate(state, grounded=False, objective="Ordinary analysis")
            _, result = self._claim_and_execute(state, work)
            assert state["transport"].protected_calls == 0
            evidence = {
                "ordinary_work_item_id": work.work_item_id,
                "ordinary_result_id": result.result_id,
                "grounded_over_limit_persisted": False,
                "evidence_calls_for_ordinary_work": 0,
            }
            self._close(state)
            return self._pass(
                "GSI-003", evidence, "closed-profile", "fail-fast-bound", "ordinary-isolation"
            )

    def _gsi_004(self):
        reset_runtime_database()
        with tempfile.TemporaryDirectory() as directory:
            state = self._composition(directory)
            work = self._delegate(state)
            first = state["runtime"].claim_work(
                work_item_id=work.work_item_id,
                scout_binding_id=state["scout_binding"].binding_id,
                workload=state["scout_workload"],
                idempotency_key="claim-one",
            )
            with state["runtime"].repository.transaction(
                lock_keys=state["runtime"]._work_lock_keys(work)
            ):
                state["runtime"].repository.save_work_attempt(
                    replace(
                        first,
                        status=AttemptStatus.RUNNING,
                        attempt_stage=AttemptStage.EVIDENCE_RETRIEVAL,
                        version=2,
                    ),
                    expected_previous_version=1,
                )
            reconciled = state["runtime"].reconcile_work(
                work_item_id=work.work_item_id,
                scout_binding_id=state["scout_binding"].binding_id,
                workload=state["scout_workload"],
                idempotency_key="reconcile-one",
            )
            assert reconciled.status == WorkStatus.RETRYABLE
            abandoned = state["runtime"].repository.get_work_attempt(first.attempt_id)
            assert abandoned.error_code == "AMBIGUOUS_EVIDENCE_RETRIEVAL"
            second, result = self._claim_and_execute(state, work, "two")
            assert second.attempt_number == 2
            assert len(state["runtime"].repository.list_work_attempts(work.work_item_id)) == 2
            evidence = {
                "work_item_id": work.work_item_id,
                "abandoned_attempt_id": first.attempt_id,
                "abandoned_error_code": abandoned.error_code,
                "accepted_attempt_id": second.attempt_id,
                "result_id": result.result_id,
                "accepted_result_count": 1,
            }
            self._close(state)
            return self._pass(
                "GSI-004", evidence, "stage-aware-reconcile", "fresh-attempt", "one-result"
            )


def main() -> int:
    results = GroundedScoutAcceptanceRunner().run_all()
    print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    return 0 if all(result.status == "PASS" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
