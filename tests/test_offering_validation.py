"""Actual bounded HTTP conformance, never a live Spark dependency."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from legion_cognition.authorized import CognitionAuthorization, CognitionInvocationContext
from legion_cognition.capability import CognitionError, CognitionRequirement, CognitionRouter, digest
from legion_cognition.composition import load_catalog
from legion_cognition.deployment_observation import VllmSshObserver, bounded_process
from legion_cognition.offering_validation import Candidate, OfferingValidator, ValidationBundle, ValidationTransport, utcnow, iso
from legion_cognition.openai_compatible import TransportPolicy
from legion_kernel import Principal, PrincipalType
from tests.cognition_http import inference_server, tool_response, final_response, REASONING_SENTINEL


def candidate_config(origin):
    value = json.loads(Path("deploy/cognition.example.json").read_text())
    value["endpoints"][0]["origin"] = origin
    value["providers"][0].update(runtime_version="1", credential_reference=None)
    value["offerings"][0].update(model_id="model-a", context_window=32768)
    return value


def initial_response():
    return tool_response('{"key":"cfv_probe"}', "lookup_validation_value")


def continuation(request):
    return final_response(json.loads(request["messages"][-1]["content"])["value"])


class Observer:
    def __init__(self):
        self.calls = 0
        self.change = False
        self.stale = False

    def observe(self, candidate):
        self.calls += 1
        return {"observed_at": iso(utcnow() - timedelta(seconds=60 if self.stale else 0)),
                "identity": {"image_id": "changed" if self.change and self.calls > 1 else "stable"}}


class Authority:
    def __init__(self):
        self.decisions = []
        self.outcomes = []
        self.denied = False

    def authorize(self, context, facts):
        if self.denied:
            raise CognitionError("COGNITION_AUTHORITY_DENIED")
        result = CognitionAuthorization(str(uuid4()), "policy-v1", str(uuid4()))
        self.decisions.append(result)
        return result

    def record_outcome(self, context, facts):
        self.outcomes.append(facts)


def context():
    return CognitionInvocationContext(Principal(PrincipalType.WORKLOAD, "validator"),
                                      *(str(uuid4()) for _ in range(7)))


def transport(**kwargs):
    with unittest.TestCase().assertWarns(RuntimeWarning):
        return ValidationTransport(policy=TransportPolicy(mode="live_acceptance", acknowledge_cleartext=True,
                                   acknowledge_unauthenticated=True, **kwargs))


class OfferingValidationTests(unittest.TestCase):
    def setup_run(self, peer):
        validator = OfferingValidator(Candidate(candidate_config(peer.origin)), Observer(), transport())
        authority, invocation_context, facts = Authority(), context(), []
        return validator, dict(context=invocation_context, authority=authority, guard=lambda: None, record=facts.append)

    def test_real_http_success_new_catalog_current_schema_no_source_mutation_or_raw_content(self):
        with inference_server([initial_response(), continuation]) as peer, tempfile.TemporaryDirectory() as directory:
            config = candidate_config(peer.origin)
            original = deepcopy(config)
            validator, ports = self.setup_run(peer)
            validator.candidate = Candidate(config)
            validator.evaluate(**ports)
            bundle = ValidationBundle(Path(directory) / "bundle")
            self.addCleanup(bundle.close)
            result = SimpleNamespace(result_id=str(uuid4()), work_item_id=ports["context"].work_item_id,
                attempt_id=ports["context"].attempt_id, content_digest="a" * 64)
            path = bundle.publish(validator, accepted_result=result, guard=lambda: None)
            resources, offerings = load_catalog(path)
            self.assertNotEqual(resources.catalog_revision, config["catalog_revision"])
            record = offerings.offerings[0].validation_record
            self.assertEqual(record.runtime_version, "1")
            self.assertEqual(record.model_id, "model-a")
            self.assertEqual(config, original)
            report = (bundle.root / "report.json").read_text()
            for forbidden in (REASONING_SENTINEL, "CFV-", "cfv_probe", "call-one", "response-initial", "response-final"):
                self.assertNotIn(forbidden, report)
            self.assertEqual(len(ports["authority"].decisions), 2)
            self.assertEqual(len({d.decision_id for d in ports["authority"].decisions}), 2)
            posts = [body for _, body, _ in peer.requests if body is not None]
            self.assertEqual(len(posts), 2)
            self.assertEqual(posts[1]["messages"][-1]["tool_call_id"], posts[1]["messages"][-2]["tool_calls"][0]["id"])
            self.assertNotIn("tools", posts[1])
            self.assertFalse((bundle.root / ".catalog.pending").exists())
            with self.assertRaisesRegex(CognitionError, "ALREADY_RUN"):
                validator.evaluate(**ports)

    def test_bad_model_responses_never_publish(self):
        missing = initial_response()
        del missing["choices"][0]["message"]["reasoning"]
        mixed = initial_response()
        mixed["choices"][0]["message"]["content"] = "not separated"
        multiple = initial_response()
        multiple["choices"][0]["message"]["tool_calls"] *= 2
        variants = [missing, mixed, multiple, tool_response('{"key":"wrong"}', "lookup_validation_value"),
                    tool_response('{"key":"cfv_probe","extra":true}', "lookup_validation_value"),
                    tool_response('{"key":"cfv_probe","key":"cfv_probe"}', "lookup_validation_value"),
                    tool_response('{"key":"cfv_probe"}', "shell"), final_response("premature")]
        for first in variants:
            with self.subTest(first=variants.index(first)), inference_server([first, continuation]) as peer:
                validator, ports = self.setup_run(peer)
                with self.assertRaises(CognitionError):
                    validator.evaluate(**ports)
                self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 1)
                self.assertEqual(ports["authority"].outcomes[-1].status, "FAILED")
                self.assertIsNone(validator.catalog)
        with inference_server([initial_response(), final_response("invented")]) as peer:
            validator, ports = self.setup_run(peer)
            with self.assertRaisesRegex(CognitionError, "CONTINUATION"):
                validator.evaluate(**ports)
            self.assertIsNone(validator.catalog)

    def test_transport_failures_are_not_retried_and_audit_failure_stops_continuation(self):
        for status in (429, 503):
            with self.subTest(status=status), inference_server([(status, b"SECRET_ERROR"), initial_response()]) as peer:
                validator, ports = self.setup_run(peer)
                with self.assertRaises(CognitionError):
                    validator.evaluate(**ports)
                self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 1)
                self.assertNotIn("SECRET_ERROR", repr(validator.report))
        with inference_server([initial_response(), continuation]) as peer:
            peer.delays = [0.1]
            validator, ports = self.setup_run(peer)
            validator.transport = transport(timeout_seconds=0.01)
            with self.assertRaises(CognitionError):
                validator.evaluate(**ports)
            self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 1)
        with inference_server([initial_response(), continuation]) as peer:
            validator, ports = self.setup_run(peer)
            ports["authority"].record_outcome = lambda *args: (_ for _ in ()).throw(OSError("SECRET_AUDIT_ERROR"))
            with self.assertRaises(CognitionError):
                validator.evaluate(**ports)
            self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 1)
            self.assertNotIn("SECRET_AUDIT_ERROR", repr(validator.report))

    def test_denial_before_call_and_revocation_after_first_call(self):
        for before in (True, False):
            with self.subTest(before=before), inference_server([initial_response(), continuation]) as peer:
                validator, ports = self.setup_run(peer)
                authority = ports["authority"]
                authority.denied = before
                original = authority.record_outcome
                def revoke(*args):
                    original(*args)
                    authority.denied = True
                authority.record_outcome = revoke
                with self.assertRaisesRegex(CognitionError, "AUTHORITY_DENIED"):
                    validator.evaluate(**ports)
                self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 0 if before else 1)

    def test_version_discovery_stale_observation_and_deployment_change_fail_closed(self):
        for failure in ("version", "context", "stale", "drift"):
            with self.subTest(failure=failure), inference_server([initial_response(), continuation]) as peer:
                validator, ports = self.setup_run(peer)
                if failure == "version":
                    peer.version = "unmatched"
                elif failure == "context":
                    peer.models[0]["max_model_len"] = 12
                elif failure == "stale":
                    validator.observer.stale = True
                else:
                    validator.observer.change = True
                with self.assertRaises(CognitionError):
                    validator.evaluate(**ports)
                self.assertIsNone(validator.catalog)
                self.assertEqual(sum(body is not None for _, body, _ in peer.requests), 2 if failure == "drift" else 0)

    def test_expired_normal_catalog_stays_fail_closed_before_network(self):
        with inference_server() as peer, tempfile.TemporaryDirectory() as directory:
            config = candidate_config(peer.origin)
            config["enabled"] = True
            config["offerings"][0]["validation_record"].update(runtime_version="1", model_id="model-a")
            path = Path(directory) / "expired.json"
            path.write_text(json.dumps(config))
            resources, offerings = load_catalog(path)
            with self.assertRaisesRegex(CognitionError, "NO_MATCH"):
                CognitionRouter(resources, offerings, transport()).select(CognitionRequirement())
            self.assertEqual(peer.requests, [])
            self.assertEqual(json.loads(path.read_text()), config)

    def test_candidate_is_not_a_normal_offering_and_only_known_profile_accepted(self):
        from legion_cognition.capability import CognitionOfferingCatalog
        config = candidate_config("http://127.0.0.1:8000")
        candidate = Candidate(config)
        with self.assertRaises(ValueError):
            CognitionOfferingCatalog("bad", (candidate.provider,), (candidate.offering,))
        for key, value in (("runtime_family", "unknown"), ("parser_profile", "unknown"), ("enabled", False)):
            bad = deepcopy(config)
            bad["providers"][0][key] = value
            with self.subTest(key=key), self.assertRaises(CognitionError):
                Candidate(bad)

    def test_bundle_ownership_failures_and_publication_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "existing").mkdir()
            (root / "alias").symlink_to(root / "existing")
            for path in (root / "existing", root / "alias", root / "alias" / "nested"):
                with self.subTest(path=path.name), self.assertRaises(CognitionError):
                    ValidationBundle(path)
            bundle = ValidationBundle(root / "new")
            self.addCleanup(bundle.close)
            validator = OfferingValidator(Candidate(candidate_config("http://127.0.0.1:8000")), Observer(), transport())
            with self.assertRaisesRegex(CognitionError, "NOT_PASSED"):
                bundle.publish(validator, accepted_result=None, guard=lambda: None)
            self.assertFalse((bundle.root / "catalog.json").exists())
        with inference_server([initial_response(), continuation]) as peer, tempfile.TemporaryDirectory() as directory:
            validator, ports = self.setup_run(peer)
            validator.evaluate(**ports)
            validator.catalog["offerings"][0]["model_id"] = "changed"
            bundle = ValidationBundle(Path(directory) / "bundle")
            self.addCleanup(bundle.close)
            with self.assertRaisesRegex(CognitionError, "ARTIFACT_MISMATCH"):
                bundle.publish(validator, accepted_result=None, guard=lambda: None)
            self.assertFalse((bundle.root / "catalog.json").exists())


def deployment():
    return dict(container_id="a" * 64, image_id="sha256:" + "b" * 64, started_at="2026-09-22T00:00:00Z",
        running=True, model_id="model-a", max_model_len=32768, reasoning_parser="qwen3", tool_call_parser="qwen3_xml",
        auto_tool_choice=True, listen_port=8000, listen_host="0.0.0.0", network_mode="host", ports={})


class DeploymentObservationTests(unittest.TestCase):
    def test_collector_uses_only_selected_docker_fields_and_emits_no_secrets(self):
        import contextlib
        import io
        from legion_cognition.deployment_observation import COLLECTOR
        observed = {"Id": "a" * 64, "Image": "sha256:" + "b" * 64, "Path": "vllm",
            "Args": ["serve", "model-a", "--reasoning-parser", "qwen3", "--tool-call-parser=qwen3_xml",
                     "--enable-auto-tool-choice", "--max-model-len", "32768", "--api-key", "SECRET_KEY"],
            "State": {"Running": True, "StartedAt": "2026-09-22T00:00:00Z"},
            "HostConfig": {"NetworkMode": "host"}, "NetworkSettings": {"Ports": {}}}
        output = io.StringIO()
        with patch("subprocess.run", return_value=SimpleNamespace(stdout=json.dumps(observed).encode())) as run, \
                patch("sys.argv", ["collector", "vllm-server"]), contextlib.redirect_stdout(output):
            exec(COLLECTOR, {})
        self.assertNotIn("SECRET_KEY", output.getvalue())
        self.assertNotIn(".Env", run.call_args.args[0][4])
        self.assertEqual(json.loads(output.getvalue())["reasoning_parser"], "qwen3")

    def test_strict_ssh_argv_and_deployment_profile(self):
        candidate = Candidate(candidate_config("http://127.0.0.1:8000"))
        commands = []
        def execute(argv):
            commands.append(argv)
            return json.dumps(deployment()).encode()
        observer = VllmSshObserver(host="127.0.0.1", user="jtdauria", container="vllm-server", execute=execute)
        result = observer.observe(candidate)
        self.assertEqual(result["identity"]["model_id"], "model-a")
        self.assertIn("StrictHostKeyChecking=yes", commands[0])
        self.assertIn("BatchMode=yes", commands[0])
        self.assertNotIn("env", result["identity"])
        for key, value in (("reasoning_parser", None), ("tool_call_parser", "other"), ("model_id", "other"),
                           ("max_model_len", 1024), ("auto_tool_choice", False), ("listen_port", 9000), ("running", False)):
            changed = {**deployment(), key: value}
            observer.execute = lambda argv: json.dumps(changed).encode()
            with self.subTest(key=key), self.assertRaises(CognitionError):
                observer.observe(candidate)

    def test_unknown_ssh_key_and_injection_never_fall_back(self):
        candidate = Candidate(candidate_config("http://127.0.0.1:8000"))
        for kwargs in ({"host": "-oBad"}, {"user": "root;id"}, {"container": "x$(id)"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(CognitionError):
                VllmSshObserver(**({"host": "127.0.0.1", "user": "jtdauria", "container": "vllm-server"} | kwargs))
        observer = VllmSshObserver(host="127.0.0.1", user="jtdauria", container="vllm-server",
            execute=lambda argv: (_ for _ in ()).throw(CognitionError("VALIDATION_OBSERVATION_UNAVAILABLE")))
        with self.assertRaisesRegex(CognitionError, "OBSERVATION_UNAVAILABLE"):
            observer.observe(candidate)

    def test_subprocess_timeout_and_output_limits(self):
        import sys
        for code, options in (("import time; time.sleep(10)", {"timeout": 0.05}),
                              ("print('x' * 10000)", {"limit": 100})):
            with self.subTest(options=options), self.assertRaises(CognitionError):
                bounded_process([sys.executable, "-c", code], **options)
