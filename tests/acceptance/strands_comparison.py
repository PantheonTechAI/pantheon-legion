"""Bounded live comparison, orchestration and recovery against synthetic Tabula.

Only test-owned state is changed. Every failed sample is retained. No adoption,
production enablement, catalog renewal or model/runtime reconfiguration occurs.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import statistics
import tempfile
import time

from aquila_api import InProcessAquilaKnowledgeAuthority
from aquila_api.runtime_authority import InProcessAquilaCognitionAuthority
from legion_cognition.capability import digest
from legion_cognition.composition import configured_cognition, load_catalog
from legion_cognition.openai_compatible import TransportPolicy
from legion_runtime import RuntimeOperationError, WorkKind
from legion_tabula import McpHttpTransport, ScopeBinding, TabulaCorpusClient
from legion_tabula.runtime_adapter import FederatedCorpusEvidenceReader
from tests import strands_fixture as fixture
from tests.acceptance.strands_live import OBJECTIVE, require
from tests.acceptance.strands_restart import write_private
from tests.federation.cognition_stack import CognitionTabulaStack
from tests.federation.fixture_server import FixtureSTSServer
from tests.runtime_postgres import reset_runtime_database, runtime_test_database_url


def safe_code(exc):
    code = getattr(exc, "code", "LIVE_SAMPLE_FAILED")
    return code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "LIVE_SAMPLE_FAILED"


def schedule():
    samples = []
    for persistence in ("P0", "P1", "P2"):
        for repetition in range(5):
            pair = persistence + "-" + str(repetition + 1)
            order = ("B0", "strands") if repetition % 2 == 0 else ("strands", "B0")
            for implementation in order:
                samples.append({"implementation": implementation, "mode": "single", "persistence": persistence,
                    "scenario": "comparison", "pair_id": pair})
    for mode in ("graph", "swarm"):
        for persistence in ("P0", "P1", "P2"):
            samples.append({"implementation": "strands", "mode": mode, "persistence": persistence,
                "scenario": "orchestration", "pair_id": None})
    for mode in ("single", "graph", "swarm"):
        for persistence in ("P0", "P1", "P2"):
            samples.append({"implementation": "strands", "mode": mode, "persistence": persistence,
                "scenario": "worker_recovery", "pair_id": None})
    samples.append({"implementation": "strands", "mode": "single", "persistence": "P0",
                    "scenario": "effect_recovery", "pair_id": None})
    return samples


def summarize(samples):
    groups = {}
    for sample in samples:
        if sample["scenario"] != "comparison":
            continue
        key = sample["implementation"] + "/" + sample.get("paired_persistence", sample["persistence"])
        groups.setdefault(key, []).append(sample)
    result = {}
    for key, values in groups.items():
        passed = [value for value in values if value["status"] == "PASS"]
        metrics = {}
        for metric in ("elapsed_ms", "provider_ms", "non_provider_ms", "prompt_tokens", "completion_tokens", "model_calls", "snapshot_bytes"):
            observed = [value[metric] for value in passed]
            metrics[metric] = ({"median": statistics.median(observed), "minimum": min(observed), "maximum": max(observed)}
                              if observed else None)
        result[key] = {"total": len(values), "passed": len(passed), "failed": len(values) - len(passed), "metrics": metrics}
    return result


def configure_live(state, config, stack, sts):
    runtime = state["runtime"]
    invoker = configured_cognition(config, InProcessAquilaCognitionAuthority(state["aquila"]),
        policy=TransportPolicy(mode="live_acceptance", acknowledge_cleartext=True,
            acknowledge_unauthenticated=True, timeout_seconds=120))
    runtime.cognition_invoker = invoker
    state.update(inference_transport=invoker.transport, inference_authority=invoker.authority, router=invoker.router)

    def issue(claims):
        # The reusable STS fixture has a deterministic clock, while real Tabula
        # validates against wall time. Advance only the fixture, never extend an
        # issued token/catalog or change Aquila's authorization decision.
        elapsed = datetime.now(timezone.utc) - sts.current_time
        if elapsed > timedelta(0):
            sts.advance(elapsed)
        claims = dict(claims)
        claims["issued_at"] = sts.current_time.isoformat().replace("+00:00", "Z")
        claims["expires_at"] = (sts.current_time + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        return sts.issue_token(claims)

    runtime.evidence_reader = FederatedCorpusEvidenceReader(
        client=TabulaCorpusClient(McpHttpTransport(stack.mcp_endpoint)),
        authority=InProcessAquilaKnowledgeAuthority(state["aquila"], issue),
        binding=ScopeBinding("33333333-3333-4333-8333-333333333333", "1.0.0"))


def run_sample(sample, config, stack, sts, seed):
    report = {**sample, "status": "FAIL", "objective_digest": digest(OBJECTIVE),
              "evidence_content_digest": seed["content_digest"], "snapshot_bytes": 0, "requests": []}
    if sample["implementation"] == "B0":
        report.update(paired_persistence=sample["persistence"], persistence="NONE")
    resources, _ = load_catalog(config)
    reset_runtime_database()
    with tempfile.TemporaryDirectory(prefix="legion-live-comparison-") as directory:
        runner, state = fixture.composition(directory, resources.endpoints[0].origin)
        driver = None
        work = None
        started = time.monotonic()
        try:
            configure_live(state, config, stack, sts)
            knowledge_authority = state["runtime"].evidence_reader.authority
            record_outcome = knowledge_authority.record_outcome
            def observed_outcome(*args, **kwargs):
                code = kwargs.get("error_code")
                if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code):
                    report.setdefault("retrieval_failure_codes", []).append(code)
                return record_outcome(*args, **kwargs)
            knowledge_authority.record_outcome = observed_outcome
            action = sample["scenario"] == "effect_recovery"
            if sample["implementation"] == "strands":
                driver = fixture.install_driver(state, directory, mode=sample["mode"],
                    persistence=sample["persistence"], action=action)
                if action:
                    fixture.enable_review(runner, state, driver)
                work = fixture.delegate(state, OBJECTIVE)
            else:
                work = state["runtime"].delegate_work(centurion_binding_id=state["centurion_binding"].binding_id,
                    workload=state["centurion_workload"], scout_assignment_id=state["scout_assignment"].assignment_id,
                    objective=OBJECTIVE, required_capabilities=("read_only_analysis", "model_reasoning", "tabula_corpus_read"),
                    correlation_id=state["scout_binding"].correlation_id, idempotency_key="baseline",
                    work_kind=WorkKind.TOOL_ASSISTED_CORPUS_ANALYSIS)
            report.update(work_item_id=work.work_item_id, agent_id=work.scout_agent_id, mission_id=work.mission_id)
            original = state["inference_transport"].chat

            def measured(endpoint, provider, offering, messages, **kwargs):
                request = {"messages": messages, "tools": kwargs.get("tools", ())}
                observation = {"request_digest": digest(request),
                    "request_bytes": len(json.dumps(request, ensure_ascii=False).encode()), "status": "FAILED"}
                report["requests"].append(observation)
                start = time.monotonic()
                try:
                    response = original(endpoint, provider, offering, messages, **kwargs)
                    observation.update(status="SUCCESS", prompt_tokens=response.prompt_tokens,
                        completion_tokens=response.completion_tokens, reasoning_tokens=response.reasoning_tokens)
                    return response
                except Exception as exc:
                    observation["error_code"] = safe_code(exc)
                    raise
                finally:
                    observation["latency_ms"] = round((time.monotonic() - start) * 1000)

            state["inference_transport"].chat = measured
            started = time.monotonic()
            if action:
                try:
                    runner._claim_and_execute(state, work, "approval")
                except RuntimeOperationError as exc:
                    require(exc.code == "SPIKE_APPROVAL_PENDING", "LIVE_APPROVAL_NOT_REACHED")
                else:
                    require(False, "LIVE_PREMATURE_EFFECT")
                require(driver.enforcer.connection.execute("SELECT count(*) FROM review_markers").fetchone()[0] == 0,
                        "LIVE_PREMATURE_EFFECT")
                report["approval_id"] = fixture.approve(runner, state, driver)
                fixture.reconcile(state, driver, work, "approved")

                def kill_after_effect():
                    execution = driver.session.execution_id
                    driver.worker.stop_owned("legion-strands-" + execution, execution)
                    raise OSError("SYNTHETIC_POST_EFFECT_KILL")

                driver.enforcer.after_commit = kill_after_effect
                try:
                    runner._claim_and_execute(state, work, "effect-kill")
                except RuntimeOperationError:
                    pass
                else:
                    require(False, "LIVE_KILL_NOT_OBSERVED")
                receipts = [row[0] for row in driver.enforcer.connection.execute("SELECT receipt_id FROM review_markers")]
                require(len(receipts) == 1, "LIVE_EFFECT_COUNT_MISMATCH")
                require(state["runtime"].get_work_result(work.work_item_id) is None, "LIVE_PREMATURE_RESULT")
                driver.enforcer.after_commit = lambda: None
                fixture.reconcile(state, driver, work, "effect-recovery")
                _, result = runner._claim_and_execute(state, work, "effect-recovery")
                after = [row[0] for row in driver.enforcer.connection.execute("SELECT receipt_id FROM review_markers")]
                require(after == receipts and driver.session.action_receipt == receipts[0], "LIVE_DUPLICATE_EFFECT")
                report.update(effect_count=1, receipt_id=receipts[0], hard_worker_kill=True)
            elif sample["scenario"] == "worker_recovery":
                killed = []

                def kill_before_response(*args, **kwargs):
                    response = measured(*args, **kwargs)
                    if response.finish_reason == "stop" and not killed:
                        killed.append(driver.session.execution_id)
                        driver.worker.stop_owned("legion-strands-" + killed[0], killed[0])
                    return response

                state["inference_transport"].chat = kill_before_response
                try:
                    runner._claim_and_execute(state, work, "kill")
                except RuntimeOperationError:
                    pass
                else:
                    require(False, "LIVE_KILL_NOT_OBSERVED")
                require(bool(killed), "LIVE_KILL_NOT_REACHED")
                require(state["runtime"].get_work_result(work.work_item_id) is None, "LIVE_PREMATURE_RESULT")
                fixture.reconcile(state, driver, work, "replacement")
                state["inference_transport"].chat = measured
                _, result = runner._claim_and_execute(state, work, "replacement")
                require(driver.session.execution_id != killed[0], "LIVE_EXECUTION_ID_REUSED")
                report.update(hard_worker_kill=True, restored=driver.restored, prior_execution_id=killed[0])
            else:
                _, result = runner._claim_and_execute(state, work)
            report["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            repository = state["runtime"].repository
            references = repository.list_work_evidence_references(work_item_id=work.work_item_id)
            require(seed["review_code"] in result.summary and "aquila" in result.summary.lower(), "LIVE_CODE_MISMATCH")
            require("OUT_OF_SCOPE_CONTROL" not in result.summary, "LIVE_CONTROL_LEAK")
            require(bool(result.evidence_references) and {r.external_record_id for r in references} == {seed["record_id"]}
                    and set(result.evidence_references).issubset({r.evidence_reference_id for r in references}),
                    "LIVE_PROVENANCE_MISMATCH")
            report.update(status="PASS", result_id=result.result_id, result_digest=result.content_digest,
                attempt_id=result.attempt_id, review_code_matched=True, out_of_scope_excluded=True,
                supporting_reference_count=len(result.evidence_references))
        except Exception as exc:
            report["error_code"] = safe_code(exc)
        finally:
            report.setdefault("elapsed_ms", round((time.monotonic() - started) * 1000))
            try:
                if work:
                    repository = state["runtime"].repository
                    if driver:
                        trial = repository.get_spike_trial(work.work_item_id)
                        operations = repository.list_spike_operations(work.work_item_id)
                        models = [op.facts for op in operations if op.kind == "MODEL"]
                        report.update(operation_statuses=[{"kind": op.kind, "status": op.status} for op in operations],
                            telemetry=driver.telemetry, trace_id=trial.trace_id if trial else None,
                            selection=trial.selection if trial else None, reserved_calls=trial.model_calls if trial else 0,
                            output_reserved=trial.output_reserved if trial else 0, attempts_started=trial.attempts_started if trial else 0)
                        if driver.state_store:
                            report["snapshot_bytes"] = sum(p.stat().st_size for p in driver.state_store.root.rglob("*.json"))
                    else:
                        models = repository.list_cognition_turns(work.work_item_id)
                        report["catalog_revision"] = models[-1]["catalog_revision"] if models else None
                    decisions = [model["decision_id"] for model in models if model.get("decision_id")]
                    report["inference_decision_ids"] = decisions
                    audit = state["aquila"].store.get_audit(work.mission_id)
                    report["knowledge_decision_ids"] = [event.data["decision_id"] for event in audit
                        if event.event_type == "EXTERNAL_READ_AUTHORIZATION_EVALUATED"]
                    if report["status"] == "PASS":
                        require(len(decisions) == len(report["requests"]) and len(set(decisions)) == len(decisions),
                                "LIVE_DECISION_COUNT_MISMATCH")
                        require(bool(report["knowledge_decision_ids"]), "LIVE_KNOWLEDGE_DECISIONS_MISSING")
            except Exception as exc:
                report.update(status="FAIL", error_code=safe_code(exc))
            finally:
                if driver and driver.enforcer:
                    driver.enforcer.close()
                runner._close(state)
    calls = report["requests"]
    report.update(model_calls=len(calls), provider_ms=sum(call["latency_ms"] for call in calls),
        prompt_tokens=sum(call.get("prompt_tokens", 0) for call in calls),
        completion_tokens=sum(call.get("completion_tokens", 0) for call in calls),
        reasoning_tokens=sum(call.get("reasoning_tokens", 0) for call in calls))
    report["non_provider_ms"] = max(0, report["elapsed_ms"] - report["provider_ms"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "tabula-root", "env-file", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--suite", choices=("all", "comparison", "profiles", "effect"), default="all")
    for name in ("execute", "reset-test-database", "acknowledge-cleartext", "acknowledge-unauthenticated", "approve-synthetic-marker"):
        parser.add_argument("--" + name, action="store_true")
    args = parser.parse_args(argv)
    if not all((args.execute, args.reset_test_database, args.acknowledge_cleartext, args.acknowledge_unauthenticated)):
        parser.error("requires explicit execution/reset and both development acknowledgements")
    if args.suite in {"all", "effect"} and not args.approve_synthetic_marker:
        parser.error("effect trial requires --approve-synthetic-marker for trusted test-operator approval")
    runtime_test_database_url()
    resources, _ = load_catalog(args.config)
    args.output.mkdir(mode=0o700)
    stack = CognitionTabulaStack(args.tabula_root, args.project_name, args.env_file)
    samples = []
    report = {"status": "FAIL", "catalog_revision": resources.catalog_revision, "suite": args.suite,
              "sdk_version": "1.56.0", "disposable_stack_removed": False}
    selected = [sample for sample in schedule() if args.suite == "all" or
        (args.suite == "comparison" and sample["scenario"] == "comparison") or
        (args.suite == "profiles" and sample["scenario"] in {"orchestration", "worker_recovery"}) or
        (args.suite == "effect" and sample["scenario"] == "effect_recovery")]
    try:
        stack._preflight_command()
        try:
            with FixtureSTSServer(host="0.0.0.0") as sts:
                stack.start(sts.docker_introspection_url)
                seed = stack.seed_corpus()
                for index, sample in enumerate(selected, 1):
                    outcome = run_sample(sample, args.config, stack, sts, seed)
                    outcome.update(order=index, cache_condition="first-observed-not-cold" if index == 1 else "uncontrolled-warm")
                    samples.append(outcome)
                    write_private(args.output / ("sample-%02d.json" % index), outcome)
                    print(json.dumps({"sample": index, "scenario": sample["scenario"], "implementation": sample["implementation"],
                        "mode": sample["mode"], "persistence": sample["persistence"], "status": outcome["status"],
                        "error_code": outcome.get("error_code")}), flush=True)
                    require(outcome.get("error_code") not in {"LIVE_DUPLICATE_EFFECT", "LIVE_CONTROL_LEAK",
                        "LIVE_PREMATURE_EFFECT", "LIVE_PROVENANCE_MISMATCH", "LIVE_DECISION_COUNT_MISMATCH",
                        "SPIKE_TELEMETRY_REFUSED"}, "LIVE_SAFETY_GATE_STOPPED_RUN")
        finally:
            stack.cleanup()
            report["disposable_stack_removed"] = True
        require(len(samples) == len(selected) > 0, "LIVE_SAMPLE_SCHEDULE_INCOMPLETE")
        report["status"] = "PASS" if all(sample["status"] == "PASS" for sample in samples) else "COMPLETED_WITH_FAILURES"
    except Exception as exc:
        report["error_code"] = safe_code(exc)
    report.update(samples=len(samples), expected_samples=len(selected), comparison=summarize(samples),
        passed=sum(sample["status"] == "PASS" for sample in samples),
        failed=sum(sample["status"] != "PASS" for sample in samples),
        latency_attribution="provider versus aggregate SDK/isolation/shared-Legion time; not SDK-only overhead")
    write_private(args.output / "report.json", report)
    print(json.dumps({"status": report["status"], "report": str(args.output / "report.json")}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
