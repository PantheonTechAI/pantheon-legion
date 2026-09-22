"""Opt-in real inference + isolated Tabula proof using only synthetic Mission data."""

import argparse
from datetime import timedelta
import json
from pathlib import Path
import tempfile

from aquila_api import InProcessAquilaKnowledgeAuthority
from aquila_api.runtime_authority import InProcessAquilaCognitionAuthority
from legion_cognition.composition import configured_cognition, load_catalog
from legion_cognition.openai_compatible import TransportPolicy
from legion_runtime import RepositoryMissionOrganizationReadModel, WorkKind
from legion_tabula import McpHttpTransport, ScopeBinding, TabulaCorpusClient
from legion_tabula.runtime_adapter import FederatedCorpusEvidenceReader
from tests.federation.fixture_server import FixtureSTSServer
from tests.federation.cognition_stack import CognitionTabulaStack
from tests.runtime_postgres import reset_runtime_database, runtime_test_database_url
from tests.test_authorized_cognition import composition


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="trusted enabled catalog, not Mission input")
    parser.add_argument("--tabula-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--acknowledge-cleartext", action="store_true")
    parser.add_argument("--acknowledge-unauthenticated", action="store_true")
    args = parser.parse_args(argv)
    if not (args.execute and args.acknowledge_cleartext and args.acknowledge_unauthenticated):
        parser.error("live acceptance requires --execute and both insecure-development acknowledgements")
    runtime_test_database_url()
    resources, _ = load_catalog(args.config)
    stack = CognitionTabulaStack(args.tabula_root, args.project_name, args.env_file)
    stack._preflight_command()
    try:
        with FixtureSTSServer(host="0.0.0.0") as sts, tempfile.TemporaryDirectory() as directory:
            stack.start(sts.docker_introspection_url)
            seed = stack.seed_corpus()
            reset_runtime_database()
            runner, state = composition(directory, resources.endpoints[0].origin)
            try:
                state["runtime"].cognition_invoker = configured_cognition(args.config,
                    InProcessAquilaCognitionAuthority(state["aquila"]),
                    policy=TransportPolicy(mode="live_acceptance", acknowledge_cleartext=True,
                                           acknowledge_unauthenticated=True, timeout_seconds=120))

                def issue(claims):
                    # The disposable STS uses a frozen test clock, including during container startup.
                    claims = dict(claims)
                    claims["issued_at"] = sts.current_time.isoformat().replace("+00:00", "Z")
                    claims["expires_at"] = (sts.current_time + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
                    return sts.issue_token(claims)

                state["runtime"].evidence_reader = FederatedCorpusEvidenceReader(
                    client=TabulaCorpusClient(McpHttpTransport(stack.mcp_endpoint)),
                    authority=InProcessAquilaKnowledgeAuthority(state["aquila"], issue),
                    binding=ScopeBinding("33333333-3333-4333-8333-333333333333", "1.0.0"))
                work = state["runtime"].delegate_work(
                    centurion_binding_id=state["centurion_binding"].binding_id,
                    workload=state["centurion_workload"], scout_assignment_id=state["scout_assignment"].assignment_id,
                    objective="Find the document named Aquila architecture evidence. Report which component owns "
                              "Mission authority and give the review code stated in that document.",
                    required_capabilities=("read_only_analysis", "model_reasoning", "tabula_corpus_read"),
                    correlation_id=state["scout_binding"].correlation_id,
                    idempotency_key="live-cognitive-work", work_kind=WorkKind.TOOL_ASSISTED_CORPUS_ANALYSIS)
                attempt, result = runner._claim_and_execute(state, work)
                turns = state["runtime"].repository.list_cognition_turns(work.work_item_id)
                assert result.evidence_references and len(turns) >= 2
                assert turns[-1]["finish_reason"] == "stop"
                assert seed["review_code"] in result.summary
                assert "OUT_OF_SCOPE_CONTROL" not in result.summary
                references = state["runtime"].repository.list_work_evidence_references(work_item_id=work.work_item_id)
                assert {item.external_record_id for item in references} == {seed["record_id"]}
                assert {item.evidence_reference_id for item in references} == set(result.evidence_references)
                assert len({turn["decision_id"] for turn in turns}) == len(turns)
                audit = state["aquila"].store.get_audit(work.mission_id)
                knowledge_decisions = [event.data["decision_id"] for event in audit
                                       if event.event_type == "EXTERNAL_READ_AUTHORIZATION_EVALUATED"]
                assert len(knowledge_decisions) == 3 and len(set(knowledge_decisions)) == 3
                snapshot = RepositoryMissionOrganizationReadModel(state["runtime"].repository).snapshot(
                    organization_id=state["scout"].organization_id, workspace_id=state["scout"].workspace_id,
                    mission_id=state["mission_id"])
                assert snapshot.work[0].cognition_turns
                report = {"status": "PASS", "mission_id": work.mission_id,
                    "scout_agent_id": work.scout_agent_id, "work_item_id": work.work_item_id,
                    "attempt_id": attempt.attempt_id, "result_id": result.result_id,
                    "supporting_evidence_count": len(result.evidence_references),
                    "catalog_revision": turns[-1]["catalog_revision"],
                    "offering_id": turns[-1]["offering_id"],
                    "record_id": seed["record_id"], "content_digest": seed["content_digest"],
                    "content_bytes": seed["content_bytes"], "result_digest": result.content_digest,
                    "review_code_matched": True, "out_of_scope_excluded": True,
                    "inference_decision_ids": [turn["decision_id"] for turn in turns],
                    "knowledge_decision_ids": knowledge_decisions,
                    "tabula_audit_correlation_id": references[0].tabula_audit_correlation_id}
            finally:
                runner._close(state)
    finally:
        stack.cleanup()
    report["disposable_stack_removed"] = True
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
