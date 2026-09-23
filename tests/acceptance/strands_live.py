"""Opt-in single/P0 read-only Spark + isolated Tabula + real Strands smoke trial.

Not a paired benchmark, recovery proof, or synthetic-action acceptance test.
"""

import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import tempfile
import time

from aquila_api import InProcessAquilaKnowledgeAuthority
from aquila_api.runtime_authority import InProcessAquilaCognitionAuthority
from experiments.strands.bridge import StrandsSpikeDriver
from legion_cognition.capability import CognitionError
from legion_cognition.composition import configured_cognition, load_catalog
from legion_cognition.openai_compatible import TransportPolicy
from legion_runtime import RuntimeOperationError, WorkKind
from legion_runtime.spike_contracts import SPIKE_CAPABILITIES
from legion_tabula import McpHttpTransport, ScopeBinding, TabulaCorpusClient
from legion_tabula.runtime_adapter import FederatedCorpusEvidenceReader
from tests.federation.cognition_stack import CognitionTabulaStack
from tests.federation.fixture_server import FixtureSTSServer
from tests.runtime_postgres import reset_runtime_database, runtime_test_database_url
from tests.test_authorized_cognition import composition


OBJECTIVE = ("Find the document named Aquila architecture evidence. Report which component owns "
             "Mission authority and give the review code stated in that document.")


def require(condition, code):
    if not condition:
        raise CognitionError(code)


def check_result(*, seed, result, references, trial, operations, telemetry, knowledge_decisions):
    """Inspect authoritative facts, not a model's claim that the task succeeded."""
    require(seed["review_code"] in result.summary and "aquila" in result.summary.lower(),
            "LIVE_EVIDENCE_ANSWER_MISMATCH")
    require("OUT_OF_SCOPE_CONTROL" not in result.summary, "LIVE_CONTROL_RECORD_LEAK")
    require(bool(references) and {r.external_record_id for r in references} == {seed["record_id"]}
            and {r.evidence_reference_id for r in references} == set(result.evidence_references),
            "LIVE_EVIDENCE_PROVENANCE_MISMATCH")
    models = [operation.facts for operation in operations if operation.kind == "MODEL"]
    require(2 <= len(models) == trial.model_calls <= 8
            and all(operation.status == "SUCCESS" for operation in operations)
            and all(operation.kind != "ACTION" for operation in operations)
            and models[-1]["finish_reason"] == "stop", "LIVE_OPERATION_MISMATCH")
    decisions = [fact["decision_id"] for fact in models]
    require(all(decisions) and len(set(decisions)) == len(decisions), "LIVE_INFERENCE_DECISION_MISMATCH")
    require(len(knowledge_decisions) == trial.retrievals * 3 > 0
            and len(set(knowledge_decisions)) == len(knowledge_decisions), "LIVE_KNOWLEDGE_DECISION_MISMATCH")
    require(bool(telemetry) and all(span["trace_id"] == trial.trace_id for span in telemetry),
            "LIVE_TRACE_MISMATCH")
    return {"review_code_matched": True, "out_of_scope_excluded": True,
        "record_id": seed["record_id"], "content_digest": seed["content_digest"],
        "result_id": result.result_id, "result_digest": result.content_digest,
        "supporting_evidence_count": len(references), "model_calls": len(models),
        "retrievals": trial.retrievals, "trace_id": trial.trace_id,
        "execution_id": trial.execution_id, "selection": trial.selection,
        "inference_decision_ids": decisions, "knowledge_decision_ids": knowledge_decisions,
        "prompt_tokens": sum(fact["prompt_tokens"] for fact in models),
        "completion_tokens": sum(fact["completion_tokens"] for fact in models),
        "reasoning_tokens": sum(fact["reasoning_tokens"] for fact in models),
        "model_latency_ms": [fact["latency_ms"] for fact in models],
        "telemetry": telemetry,
        "tabula_audit_correlation_ids": sorted({r.tabula_audit_correlation_id for r in references})}


def execute_trial(directory, config, stack, sts, seed, report):
    resources, _ = load_catalog(config)
    runner, state = composition(directory, resources.endpoints[0].origin)
    try:
        runtime = state["runtime"]
        runtime.cognition_invoker = configured_cognition(config,
            InProcessAquilaCognitionAuthority(state["aquila"]),
            policy=TransportPolicy(mode="live_acceptance", acknowledge_cleartext=True,
                acknowledge_unauthenticated=True, timeout_seconds=120))

        def issue(claims):
            claims = dict(claims)
            claims["issued_at"] = sts.current_time.isoformat().replace("+00:00", "Z")
            claims["expires_at"] = (sts.current_time + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
            return sts.issue_token(claims)

        runtime.evidence_reader = FederatedCorpusEvidenceReader(
            client=TabulaCorpusClient(McpHttpTransport(stack.mcp_endpoint)),
            authority=InProcessAquilaKnowledgeAuthority(state["aquila"], issue),
            binding=ScopeBinding("33333333-3333-4333-8333-333333333333", "1.0.0"))
        driver = StrandsSpikeDriver()
        runtime.experimental_driver = driver
        # This WorkKind requires the complete experimental capability tuple;
        # capabilities are not grants. No action authority/enforcer is installed.
        work = runtime.delegate_work(centurion_binding_id=state["centurion_binding"].binding_id,
            workload=state["centurion_workload"], scout_assignment_id=state["scout_assignment"].assignment_id,
            objective=OBJECTIVE, required_capabilities=SPIKE_CAPABILITIES,
            correlation_id=state["scout_binding"].correlation_id, idempotency_key="strands-live-smoke",
            work_kind=WorkKind.COGNITION_INTEGRATION_SPIKE)
        report.update(mission_id=work.mission_id, agent_id=work.scout_agent_id, work_item_id=work.work_item_id)
        started = time.monotonic()
        try:
            attempt, result = runner._claim_and_execute(state, work)
            report["attempt_id"] = attempt.attempt_id
            repository = runtime.repository
            require(not repository.list_cognition_turns(work.work_item_id), "LIVE_INCUMBENT_LEDGER_CHANGED")
            audit = state["aquila"].store.get_audit(work.mission_id)
            report.update(check_result(seed=seed, result=result,
                references=repository.list_work_evidence_references(work_item_id=work.work_item_id),
                trial=repository.get_spike_trial(work.work_item_id),
                operations=repository.list_spike_operations(work.work_item_id), telemetry=driver.telemetry,
                knowledge_decisions=[event.data["decision_id"] for event in audit
                    if event.event_type == "EXTERNAL_READ_AUTHORIZATION_EVALUATED"]))
        finally:
            report["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            # Safe ledger counts remain useful even when live behavior fails.
            operations = runtime.repository.list_spike_operations(work.work_item_id)
            report["operation_statuses"] = [{"kind": op.kind, "status": op.status} for op in operations]
    finally:
        runner._close(state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--tabula-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--report", type=Path, required=True, help="new private report file; never overwrite")
    for name in ("execute", "reset-test-database", "acknowledge-cleartext", "acknowledge-unauthenticated"):
        parser.add_argument("--" + name, action="store_true")
    args = parser.parse_args(argv)
    if not all((args.execute, args.reset_test_database, args.acknowledge_cleartext, args.acknowledge_unauthenticated)):
        parser.error("requires explicit execution, test-DB reset and both insecure-development acknowledgements")
    report = {"status": "FAIL", "profile": "single/P0/read-only", "sdk_version": "1.56.0",
              "disposable_stack_removed": False, "phase": "preflight"}
    stack = CognitionTabulaStack(args.tabula_root, args.project_name, args.env_file)
    # Exclusive creation refuses an occupied path or symlink before any side effect.
    descriptor = os.open(args.report, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        try:
            runtime_test_database_url()
            load_catalog(args.config)
            stack._preflight_command()
            try:
                with FixtureSTSServer(host="0.0.0.0") as sts, tempfile.TemporaryDirectory(prefix="legion-strands-live-") as directory:
                    report["phase"] = "stack_start"
                    stack.start(sts.docker_introspection_url)
                    report["phase"] = "seed"
                    seed = stack.seed_corpus()
                    report["phase"] = "test_database_reset"
                    reset_runtime_database()
                    report["phase"] = "workload"
                    execute_trial(directory, args.config, stack, sts, seed, report)
            finally:
                stack.cleanup()
                report["disposable_stack_removed"] = True
            report.update(status="PASS", phase="complete")
        except Exception as exc:
            # Never emit exception text, subprocess commands, model output or credentials.
            code = exc.code if isinstance(exc, (CognitionError, RuntimeOperationError)) else "STRANDS_LIVE_FAILED"
            report["error_code"] = code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "STRANDS_LIVE_FAILED"
        json.dump(report, output, sort_keys=True, indent=2)
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({"status": report["status"], "report": str(args.report)}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
