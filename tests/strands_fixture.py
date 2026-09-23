"""Trusted synthetic fixture composition shared by recovery and live experiments."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aquila_api import InProcessAquilaAgentAuthority, InProcessAquilaKnowledgeAuthority, PersistentAquilaService
from aquila_api.runtime_authority import InProcessAquilaCognitionAuthority
from aquila_api.spike_actions import SpikeActionAuthority
from experiments.strands.bridge import StrandsSpikeDriver
from experiments.strands.enforcer import ReviewMarkerFixture
from experiments.strands.state import OperationalStore
from legion_cognition.authorized import AuthorizedCognitionInvoker
from legion_cognition.capability import CognitionRouter
from legion_kernel import Principal, PrincipalType, RoeLevel
from legion_runtime import PersistentAgentRuntime, WorkKind
from legion_runtime.spike_contracts import SPIKE_CAPABILITIES
from legion_tabula import TabulaCorpusClient
from legion_tabula.runtime_adapter import FederatedCorpusEvidenceReader
from pantheon_sts import Ed25519AssertionVerifier, InMemorySecurityTokenService, sign_assertion
from tests.acceptance.grounded_scout_runner import BINDING, CORRELATION, FixtureTabulaTransport, GroundedScoutAcceptanceRunner
from tests.runtime_postgres import new_runtime_store
from tests.test_authorized_cognition import composition, development_transport
from tests.test_cognition_capability import catalog


def reopen(directory, origin, work_item_id):
    """Re-read real owner stores; do not deserialize agents, grants, or approvals."""
    runner = GroundedScoutAcceptanceRunner()
    aquila = PersistentAquilaService(str(Path(directory) / "aquila.sqlite3"))
    authority = InProcessAquilaAgentAuthority(aquila)
    key = Ed25519PrivateKey.generate()
    sts = InMemorySecurityTokenService(Ed25519AssertionVerifier({"aquila-test": key.public_key()}))
    knowledge = InProcessAquilaKnowledgeAuthority(aquila,
        lambda claims: sts.issue(sign_assertion(claims, key, key_id="aquila-test")).token)
    transport = FixtureTabulaTransport(sts)
    reader = FederatedCorpusEvidenceReader(client=TabulaCorpusClient(transport), authority=knowledge, binding=BINDING)
    runtime = PersistentAgentRuntime(new_runtime_store(), authority, mission_context=authority, evidence_reader=reader)
    work = runtime.get_work_item(work_item_id)
    if work is None or work.kind != WorkKind.COGNITION_INTEGRATION_SPIKE:
        runtime.close()
        aquila.close()
        raise ValueError("FIXTURE_WORK_NOT_FOUND")
    state = {"aquila": aquila, "runtime": runtime, "mission_id": work.mission_id, "transport": transport}
    for role in ("centurion", "scout"):
        assignment = runtime.get_assignment(getattr(work, role + "_assignment_id"))
        binding = runtime.repository.get_active_binding(assignment.assignment_id)
        state[role] = runtime.get_agent(assignment.agent_id)
        state[role + "_assignment"] = assignment
        state[role + "_binding"] = binding
        state[role + "_grant"] = binding.grant_id
        state[role + "_workload"] = Principal(PrincipalType.WORKLOAD, "gsi-" + role,
            frozenset({"MISSION_WORKER"}) if role == "scout" else frozenset())
    resources, offerings = catalog(origin)
    inference = development_transport()
    inference_authority = InProcessAquilaCognitionAuthority(aquila)
    router = CognitionRouter(resources, offerings, inference)
    runtime.cognition_invoker = AuthorizedCognitionInvoker(router, inference, inference_authority)
    state.update(inference_transport=inference, inference_authority=inference_authority, router=router)
    return runner, state, work


def install_driver(state, directory, *, mode="single", persistence="P0", action=False, gate=None):
    root = Path(directory) / "operational"
    store = None
    if persistence != "P0":
        root.mkdir(mode=0o700, exist_ok=True)
        store = OperationalStore(root, synthetic=True)
    driver = StrandsSpikeDriver(mode=mode, persistence=persistence, state_store=store, gate=gate,
        action_authority=SpikeActionAuthority(state["aquila"]) if action else None)
    state["runtime"].experimental_driver = driver
    if action:
        driver.enforcer = ReviewMarkerFixture(database=str(Path(directory) / "effects.sqlite3"),
            authority=driver.action_authority, gate=driver.gate, current_scope=driver.action_scope)
    return driver


def enable_review(runner, state, driver):
    """Trusted test operator permits only the synthetic approval scenario."""
    aquila, runtime = state["aquila"], state["runtime"]
    state["scout_workload"] = replace(state["scout_workload"], roles=frozenset({"MISSION_WORKER"}))
    for command, payload in (("START", {}), ("SET_ROE", {"level": "REVIEW", "reason": "Synthetic spike fixture only"})):
        mission = aquila.kernel.get_mission(state["mission_id"])
        result = driver.control(aquila.submit_command, actor=runner.owner, mission_id=mission.id,
            body={"command_type": command, "expected_version": mission.version,
                  "idempotency_key": "fixture-" + command, "payload": payload})
        if result.status_code != 200:
            raise ValueError("FIXTURE_REVIEW_SETUP_FAILED")
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    for role in ("centurion", "scout"):
        operations = {"READ_MISSION"} if role == "centurion" else {
            "READ_MISSION", "READ_KNOWLEDGE", "INVOKE_COGNITION", "EXECUTE_ACTION"}
        grant = driver.control(aquila.issue_delegation, issuer=runner.owner,
            subject=state[role + "_workload"], mission_id=state["mission_id"],
            allowed_operations=frozenset(operations), roe_ceiling=RoeLevel.REVIEW, expires_at=expiry)
        binding = driver.control(runtime.resume_assignment, assignment_id=state[role + "_assignment"].assignment_id,
            workload=state[role + "_workload"], delegation_id=grant, correlation_id=CORRELATION,
            idempotency_key="fixture-review-" + role).binding
        state[role + "_binding"], state[role + "_grant"] = binding, grant


def delegate(state, objective="Find architecture evidence", suffix="fixture"):
    return state["runtime"].delegate_work(centurion_binding_id=state["centurion_binding"].binding_id,
        workload=state["centurion_workload"], scout_assignment_id=state["scout_assignment"].assignment_id,
        objective=objective, required_capabilities=SPIKE_CAPABILITIES, correlation_id=CORRELATION,
        idempotency_key="delegate-" + suffix, work_kind=WorkKind.COGNITION_INTEGRATION_SPIKE)


def approve(runner, state, driver):
    approvals = state["aquila"]._list_persisted_approvals(state["mission_id"])
    if len(approvals) != 1 or approvals[0].status != "PENDING":
        raise ValueError("FIXTURE_APPROVAL_NOT_PENDING")
    approval = approvals[0]
    response = driver.control(state["aquila"].decide_approval, actor=runner.owner, mission_id=state["mission_id"],
        body={"approval_id": approval.id, "expected_mission_version": approval.mission_version,
              "decision": "APPROVE", "reason": "Trusted test operator approves only the synthetic reviewed marker"})
    if response.status_code != 200:
        raise ValueError("FIXTURE_APPROVAL_FAILED")
    return approval.id


def reconcile(state, driver, work, suffix):
    return driver.control(state["runtime"].reconcile_work, work_item_id=work.work_item_id,
        scout_binding_id=state["scout_binding"].binding_id, workload=state["scout_workload"],
        idempotency_key="reconcile-" + suffix)


def close(runner, state, driver):
    if driver.enforcer:
        driver.enforcer.close()
    runner._close(state)
