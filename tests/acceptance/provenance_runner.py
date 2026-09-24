"""Opt-in real Tabula and SIGKILL/reconstruction proof for PER-001."""

import argparse
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4
import select
import signal
import subprocess
import sys
import tempfile
import threading
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from aquila_api import InProcessAquilaAgentAuthority, InProcessAquilaKnowledgeAuthority, PersistentAquilaService
from aquila_api.runtime_authority import InProcessAquilaCognitionAuthority
from legion_cognition.authorized import AuthorizedCognitionInvoker
from legion_cognition.capability import CognitionRouter
from legion_kernel import Principal, PrincipalType
from legion_runtime import PersistentAgentRuntime, RuntimeOperationError
from legion_runtime.evidence import GroundedEvidenceRereadRequest, EvidenceReadError
from legion_runtime.provenance import ProvenanceAssessment, checkpoint_references
from legion_tabula import McpHttpTransport, ScopeBinding, TabulaCorpusClient
from legion_tabula.corpus import CorpusReference
from legion_tabula.runtime_adapter import FederatedCorpusEvidenceReader
from pantheon_sts import sign_assertion
from tests.cognition_http import inference_server, final_response
from tests.federation.cognition_stack import CognitionTabulaStack
from tests.federation.fixture_server import FixtureSTSServer
from tests.runtime_postgres import new_runtime_store, reset_runtime_database, runtime_test_database_url
from tests.test_authorized_cognition import composition, development_transport
from tests.test_cognition_capability import catalog
from tests.test_provenance_runtime import delegate


SENTINEL = "PER001_RAW_PRIVATE_SENTINEL_"
BINDING = ScopeBinding("33333333-3333-4333-8333-333333333333", "1.0.0")


class CountingTransport(McpHttpTransport):
    def __init__(self, endpoint):
        super().__init__(endpoint, max_response_bytes=1024 * 1024)
        self.tools = []
        self.allow_search = True

    def __call__(self, token, request):
        if not self.allow_search and request["name"] == "legion_search_corpus":
            raise RuntimeError("RECOVERY_SEARCH_FORBIDDEN")
        self.tools.append(request["name"])
        return super().__call__(token, request)


def build_runtime(payload):
    aquila = PersistentAquilaService(str(Path(payload["directory"]) / "aquila.sqlite3"))
    authority = InProcessAquilaAgentAuthority(aquila)
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(payload["signing_key"]))
    def issue(claims):
        claims = dict(claims, issued_at=payload["issued_at"], expires_at=payload["expires_at"])
        assertion = sign_assertion(claims, key, key_id="aquila-fixture")
        request = Request(payload["sts_url"] + "/v1/delegated-tokens",
            data=json.dumps({"assertion": assertion}).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Pantheon-Service": "aquila"})
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read())["token"]
    transport = CountingTransport(payload["mcp_endpoint"])
    reader = FederatedCorpusEvidenceReader(client=TabulaCorpusClient(transport),
        authority=InProcessAquilaKnowledgeAuthority(aquila, issue), binding=BINDING)
    http = development_transport()
    resources, offerings = catalog(payload["inference_origin"])
    invoker = AuthorizedCognitionInvoker(CognitionRouter(resources, offerings, http), http,
                                        InProcessAquilaCognitionAuthority(aquila))
    runtime = PersistentAgentRuntime(new_runtime_store(), authority, mission_context=authority,
                                    evidence_reader=reader, cognition_invoker=invoker)
    return aquila, runtime, transport


def worker():
    payload = json.load(sys.stdin)  # Ephemeral fixture signing key, never a file or report.
    aquila, runtime, transport = build_runtime(payload)
    workload = Principal(PrincipalType.WORKLOAD, payload["workload"])
    kwargs = dict(work_item_id=payload["work_item_id"], scout_binding_id=payload["binding_id"], workload=workload)
    try:
        if payload["recover"]:
            transport.allow_search = False
            runtime.reconcile_work(**kwargs, idempotency_key="per-real-reconcile")
        else:
            def checkpoint_boundary(self, request, running):
                print(json.dumps({"checkpoint_committed": True, "tools": transport.tools}), flush=True)
                threading.Event().wait()  # The parent must destroy this process with SIGKILL.
            ProvenanceAssessment.finish = checkpoint_boundary
        attempt = runtime.claim_work(**kwargs, idempotency_key="claim-recovery" if payload["recover"] else "claim-initial")
        result = runtime.execute_scout_work(**kwargs, idempotency_key="execute-recovery" if payload["recover"] else "execute-initial")
        print(json.dumps({"result_id": result.result_id, "attempt_id": attempt.attempt_id,
                          "citations": result.evidence_references, "tools": transport.tools}), flush=True)
    finally:
        runtime.close()
        aquila.close()


def fixture(stack, action, record_id=None):
    source = (stack.tabula_root / "tests/federation/provenance_fixture.py").read_text()
    ingest = (stack.tabula_root / "ingest/ingest.py").read_text() if action == "ingest" else None
    script = source + "\nimport json\nprint(json.dumps(execute(" + repr(action) + ", " + repr(record_id) + ", " + repr(ingest) + ")))\n"
    result = stack.runner(stack._compose_prefix + ["exec", "-T", "mcp-server", "python", "-"],
        cwd=stack.tabula_root, env=stack._environment, input=script,
        text=True, capture_output=True, check=True, timeout=60)
    return json.loads(result.stdout.splitlines()[-1])


def run_worker(payload, *, kill_at_checkpoint=False):
    process = subprocess.Popen([sys.executable, "-B", "-m", __name__ if __name__ != "__main__" else "tests.acceptance.provenance_runner", "--worker"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        process.stdin.write(json.dumps(payload))
        process.stdin.close()
        process.stdin = None
        if kill_at_checkpoint:
            ready, _, _ = select.select([process.stdout], [], [], 45)
            if not ready:
                raise RuntimeError("CHECKPOINT_TIMEOUT")
            line = process.stdout.readline()
            if not line:
                print("Worker diagnostic: " + process.stderr.read()[-4000:], file=sys.stderr)
                raise RuntimeError("CHECKPOINT_WORKER_FAILED")
            result = json.loads(line)
            if not result.get("checkpoint_committed"):
                raise RuntimeError("CHECKPOINT_NOT_COMMITTED")
            process.kill()
            process.wait(timeout=10)
            assert process.returncode == -signal.SIGKILL
            result["exit_signal"] = "SIGKILL"
            return result
        output, diagnostic = process.communicate(timeout=60)
        if process.returncode:
            print("Worker diagnostic: " + diagnostic[-4000:], file=sys.stderr)
            raise RuntimeError("RECOVERY_WORKER_FAILED")
        return json.loads(output.splitlines()[-1])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def execute(directory, stack, sts, peer, report):
    seed = fixture(stack, "seed")
    report["backend_probe"] = fixture(stack, "backend_probe", seed["record_ids"][0])
    runner, state = composition(directory, peer.origin)
    try:
        runtime = state["runtime"]
        work = delegate(state, objective="PER001 evidence")
        payload = {"directory": directory, "work_item_id": work.work_item_id,
            "binding_id": state["scout_binding"].binding_id, "workload": state["scout_workload"].subject,
            "mcp_endpoint": stack.mcp_endpoint, "sts_url": sts.base_url,
            "signing_key": sts._private_key.private_bytes_raw().hex(),
            "issued_at": sts.current_time.isoformat(), "expires_at": (sts.current_time + timedelta(minutes=5)).isoformat(),
            "inference_origin": peer.origin, "recover": False}
        first = run_worker(payload, kill_at_checkpoint=True)
        retained = runtime.repository.get_work_item(work.work_item_id)
        original = checkpoint_references(runtime.repository, retained)
        report.update(initial_record_count=len(original), initial_byte_counts=[ref.content_bytes for ref in original])
        assert len(original) == 5 and min(ref.content_bytes for ref in original) < 100
        assert {ref.external_record_id for ref in original} == set(seed["record_ids"])
        assert first["tools"] == ["legion_search_corpus"]
        result = run_worker(dict(payload, recover=True))
        assert result["tools"] == ["legion_reread_corpus"]
        accepted = runtime.repository.get_work_result(work.work_item_id)
        assert accepted.result_id == result["result_id"] and accepted.scout_agent_id == work.scout_agent_id
        assert set(accepted.evidence_references).isdisjoint(retained.evidence_checkpoint.reference_ids)
        current = runtime.repository.list_work_evidence_references(attempt_id=accepted.attempt_id)
        by_id = {ref.external_record_id: ref for ref in current}
        assert all((ref.content_sha256, ref.content_bytes) ==
                   (by_id[ref.external_record_id].content_sha256, by_id[ref.external_record_id].content_bytes) for ref in original)
        chats = [body for _, body, _ in peer.requests if body is not None]
        assert len(chats) == 1 and "tools" not in chats[0]
        inputs = json.loads(chats[0]["messages"][-1]["content"])["untrusted_evidence"]
        assert [(item["record_id"], sha256(item["content"].encode()).hexdigest()) for item in inputs] == [
            (ref.external_record_id, ref.content_sha256) for ref in original]
        turns = runtime.repository.list_cognition_turns(work.work_item_id)
        decision_trails = [runtime.repository.get_work_attempt(attempt_id).knowledge_authorization_decision_ids
                           for attempt_id in (original[0].attempt_id, accepted.attempt_id)]
        assert [len(trail) for trail in decision_trails] == [3, 3]
        assert len(set(value for trail in decision_trails for value in trail)) == 6
        safe = repr(current) + repr(runtime.list_events(work.scout_agent_id)) + repr(turns)
        assert SENTINEL not in safe
        report.update(work_item_id=work.work_item_id, agent_id=work.scout_agent_id,
            first_attempt_id=original[0].attempt_id, accepted_attempt_id=accepted.attempt_id,
            result_id=accepted.result_id, record_count=len(original), byte_counts=[ref.content_bytes for ref in original],
            checkpoint_unchanged=runtime.repository.get_work_item(work.work_item_id).evidence_checkpoint == retained.evidence_checkpoint,
            initial_tools=first["tools"], recovery_tools=result["tools"], exit_signal=first["exit_signal"],
            inference_decision_ids=[turn["decision_id"] for turn in turns],
            knowledge_decision_ids=[list(trail) for trail in decision_trails],
            raw_content_absent_from_runtime_facts=True)
        # Test the real endpoint's refusal behavior under the same authorized scope.
        authority, probe, transport = build_runtime(payload)
        try:
            context = GroundedEvidenceRereadRequest(
                state["scout"].organization_id, state["scout"].workspace_id, work.mission_id,
                work.scout_agent_id, work.scout_assignment_id, state["scout_workload"],
                state["scout_grant"], work.work_item_id, accepted.attempt_id,
                work.correlation_id, original)
            # Exercise invalid arguments through real FastMCP middleware and audit.
            arguments = {"schema_version": "1.0", "request_id": str(uuid4()),
                "correlation_id": work.correlation_id, "binding": BINDING.payload(),
                "intent": "SCOUT_EVIDENCE", "projection": "utf8-prefix-v1",
                "references": [CorpusReference(ref.external_record_id, ref.external_revision,
                    ref.canonical_uri, ref.content_bytes, ref.content_sha256).payload() for ref in original]}
            invalid = dict(arguments, query="PER001_INVALID_PRIVATE_SENTINEL")
            def credential():
                return probe.evidence_reader.authority.authorize_operation(context, BINDING).token
            response = transport(credential, {"name": "legion_reread_corpus", "arguments": invalid})
            assert response.body["code"] == "INVALID_REQUEST"
            assert response.body["request_id"] == arguments["request_id"]
            report["real_invalid_request_refused"] = True
            outcomes = {}
            report["real_mutation_refusals"] = outcomes
            target = original[0].external_record_id
            for mutation in ("revision", "changed", "scope", "noop", "ingest", "delete"):
                fixture(stack, "restore", target)
                mutation_result = fixture(stack, mutation, target)
                report.setdefault("mutation_metadata", {})[mutation] = mutation_result
                try:
                    probe.evidence_reader.reread(context)
                except EvidenceReadError as exc:
                    outcomes[mutation] = exc.code
                    assert exc.code == "EVIDENCE_REREAD_UNAVAILABLE"
                else:
                    raise AssertionError("MUTATED_RECORD_ACCEPTED")
                if mutation == "ingest":
                    assert not mutation_result["revision_present"]
                if mutation == "delete":
                    assert mutation_result["replacement_id"] != target
            report["tabula_audit"] = fixture(stack, "audit")
            logs = stack.runner(stack._compose_prefix + ["logs", "--no-color", "mcp-server", "console", "rushdb"],
                cwd=stack.tabula_root, env=stack._environment, capture_output=True, text=True, check=True)
            assert all(value not in logs.stdout + logs.stderr for value in
                       (SENTINEL, "PER001_INVALID_PRIVATE_SENTINEL", "pts_", payload["signing_key"]))
            report["raw_sentinels_absent_from_service_logs"] = True
            safe += repr(authority.store.get_audit(work.mission_id))
            assert all(value not in safe for value in (SENTINEL, "pts_", payload["signing_key"]))
            report["raw_sentinels_absent_from_aquila_audit"] = True
        finally:
            probe.close()
            authority.close()
    finally:
        runner._close(state)


def source_snapshot(root):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    changed = set(git("diff", "--name-only", "HEAD").splitlines())
    changed.update(git("ls-files", "--others", "--exclude-standard").splitlines())
    return {"commit": git("rev-parse", "HEAD"), "changed_file_sha256": {
        name: sha256((root / name).read_bytes()).hexdigest() for name in sorted(changed)
        if (root / name).is_file() and not Path(name).name.startswith(".env")}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--reset-test-database", action="store_true")
    parser.add_argument("--tabula-root", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--project-name")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.worker:
        try:
            worker()
        except Exception as exc:
            import traceback
            # No exception messages, locals, arguments, or credentials.
            frames = traceback.extract_tb(exc.__traceback__)
            print(json.dumps({"type": type(exc).__name__,
                "code": exc.code if isinstance(exc, (RuntimeOperationError, EvidenceReadError)) else None,
                "frames": [{"file": Path(f.filename).name, "line": f.lineno, "function": f.name} for f in frames]}), file=sys.stderr)
            return 1
        return 0
    if not all((args.execute, args.reset_test_database, args.tabula_root, args.env_file, args.project_name, args.report)):
        parser.error("explicit execution, owned test DB reset, isolated Tabula configuration and new report required")
    report = {"status": "FAIL", "profile": "PER-001", "disposable_stack_removed": False, "phase": "preflight"}
    descriptor = os.open(args.report, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    stack = CognitionTabulaStack(args.tabula_root, args.project_name, args.env_file)
    with os.fdopen(descriptor, "w") as output:
        try:
            runtime_test_database_url()
            report["sources"] = {"legion": source_snapshot(Path.cwd()), "tabula": source_snapshot(args.tabula_root)}
            shared = Path("tests/contracts/tabula-corpus-reread-v1.json").read_bytes()
            assert shared == (args.tabula_root / "tests/federation/corpus-reread-v1.json").read_bytes()
            report["shared_fixture_sha256"] = sha256(shared).hexdigest()
            report["inference"] = "deterministic local HTTP fixture through AuthorizedCognitionInvoker"
            report["limits"] = {"records": 8, "record_bytes": 8192, "bundle_bytes": 32768,
                                "wire_bytes": 1048576, "post_auth_seconds": 7}
            stack._preflight_command()
            try:
                with FixtureSTSServer(host="0.0.0.0") as sts, inference_server([final_response()]) as peer, tempfile.TemporaryDirectory(prefix="per001-runtime-") as directory:
                    report["phase"] = "stack_start"
                    stack.start(sts.docker_introspection_url)
                    reset_runtime_database()
                    report["phase"] = "recovery_and_mutation_proof"
                    execute(directory, stack, sts, peer, report)
            finally:
                stack.cleanup()
                for operation in (["ps", "--all", "--quiet"], ["volume", "ls", "--quiet"], ["network", "ls", "--quiet"]):
                    remaining = subprocess.check_output(["docker", *operation, "--filter",
                        "label=com.docker.compose.project=" + args.project_name], text=True)
                    assert not remaining.strip()
                report["disposable_stack_removed"] = True
            report.update(status="PASS", phase="complete")
        except Exception as exc:
            import traceback
            report["error_frames"] = [{"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                                      for f in traceback.extract_tb(exc.__traceback__)]
            report["error_type"] = type(exc).__name__
            if isinstance(exc, (RuntimeOperationError, EvidenceReadError)):
                report["error_code"] = exc.code
        json.dump(report, output, indent=2, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    print(json.dumps({"status": report["status"], "report": str(args.report)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
