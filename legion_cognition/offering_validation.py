"""Fixed, freshly authorized maintenance probes; never a normal routing path."""

from dataclasses import asdict, dataclass, replace
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import time
from uuid import uuid4

from legion_resource.inference import ComputeNode, InferenceEndpoint, identifier, positive, timestamp
from .authorized import CognitionInvocationFacts
from .capability import CognitionError, CognitionSelection, OfferingValidationRecord, InferenceProvider, digest
from .openai_compatible import OpenAICompatibleTransport, strict_json


SUITE = "legion-offering-conformance-v1"
FEATURES = ("reasoning", "tool_calls", "separated_reasoning")
TOOL = {"type": "function", "function": {"name": "lookup_validation_value",
    "description": "Read the synthetic value needed to answer this conformance probe.",
    "parameters": {"type": "object", "properties": {"key": {"type": "string", "enum": ["cfv_probe"]}},
                   "required": ["key"], "additionalProperties": False}}}


def utcnow():
    return datetime.now(timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def require(condition, code):
    if not condition:
        raise CognitionError(code)


@dataclass(frozen=True)
class CandidateOffering:
    """Not a ModelOffering: cannot be installed in the ordinary typed router."""

    offering_id: str
    provider_id: str
    model_id: str
    context_window: int
    features: tuple[str, ...]


class Candidate:
    def __init__(self, config):
        try:
            require(set(config) == {"enabled", "catalog_revision", "nodes", "endpoints", "providers", "offerings"},
                    "VALIDATION_CANDIDATE_INVALID")
            require(type(config["enabled"]) is bool, "VALIDATION_CANDIDATE_INVALID")
            identifier(config["catalog_revision"])
            require(all(isinstance(config[k], list) and len(config[k]) == 1
                        for k in ("nodes", "endpoints", "providers", "offerings")), "VALIDATION_SINGLE_OFFERING_REQUIRED")
            self.node = ComputeNode(**config["nodes"][0])
            self.endpoint = InferenceEndpoint(**config["endpoints"][0])
            self.provider = InferenceProvider(**config["providers"][0])
            item = config["offerings"][0]
            require(set(item) <= {"offering_id", "provider_id", "model_id", "context_window", "features",
                                  "priority", "enabled", "data_classifications", "validation_record"},
                    "VALIDATION_CANDIDATE_INVALID")
            for key in ("offering_id", "provider_id", "model_id"):
                identifier(item[key])
            positive(item["context_window"])
            positive(item.get("priority", 100))
            require(item.get("enabled", True) is True and self.node.enabled and self.endpoint.enabled
                    and self.provider.enabled and self.node.locality == "LOCAL", "VALIDATION_CANDIDATE_DISABLED")
            require(item.get("data_classifications", ["internal"]) == ["internal"]
                    and item["features"] == list(FEATURES), "VALIDATION_PROFILE_UNSUPPORTED")
            require(self.provider.runtime_family == "vllm" and self.provider.parser_profile == "qwen3-qwen3_xml-auto",
                    "VALIDATION_PROFILE_UNSUPPORTED")
            require(self.endpoint.node_id == self.node.node_id and self.provider.endpoint_id == self.endpoint.endpoint_id
                    and item["provider_id"] == self.provider.provider_id, "VALIDATION_CANDIDATE_INVALID")
            self.offering = CandidateOffering(*(item[k] for k in ("offering_id", "provider_id", "model_id", "context_window")), FEATURES)
            # Prior validation is untrusted candidate data, not proof or a clock override.
            self.source_digest = digest(config)
            self.source_revision = config["catalog_revision"]
            self.priority = item.get("priority", 100)
        except CognitionError:
            raise
        except (ValueError, TypeError, KeyError):
            raise CognitionError("VALIDATION_CANDIDATE_INVALID") from None

    @classmethod
    def read(cls, path):
        try:
            with Path(path).open("rb") as source:
                body = source.read(65537)
            require(len(body) <= 65536, "VALIDATION_CANDIDATE_INVALID")
            return cls(strict_json(body))
        except (OSError, ValueError, TypeError, UnicodeError):
            raise CognitionError("VALIDATION_CANDIDATE_INVALID") from None

    def selection(self, revision):
        return CognitionSelection(revision, self.offering.offering_id, self.provider.provider_id,
                                  self.endpoint.endpoint_id, self.node.node_id)

    def validated_catalog(self, revision, completed):
        record = OfferingValidationRecord(self.provider.provider_id, self.provider.runtime_family,
            self.provider.runtime_version, self.offering.model_id, self.provider.parser_profile,
            FEATURES, iso(completed), iso(completed + timedelta(hours=24)))
        return {"enabled": True, "catalog_revision": revision, "nodes": [asdict(self.node)],
                "endpoints": [asdict(self.endpoint)], "providers": [asdict(self.provider)],
                "offerings": [{**asdict(self.offering), "enabled": True, "priority": self.priority,
                               "data_classifications": ["internal"], "validation_record": asdict(record)}]}


class ValidationTransport(OpenAICompatibleTransport):
    """Reuse bounded HTTP/privacy parser, inspecting reasoning only transiently."""

    def version(self, candidate):
        try:
            value = strict_json(self._request(candidate.endpoint, candidate.provider, "/version"))
            require(value["version"] == candidate.provider.runtime_version, "VALIDATION_RUNTIME_MISMATCH")
            return value["version"]
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise CognitionError("VALIDATION_RUNTIME_INVALID") from None

    def probe(self, candidate, messages, *, initial):
        payload = {"model": candidate.offering.model_id, "messages": messages, "max_tokens": 2048,
                   "temperature": 0, "stream": False, "parallel_tool_calls": False}
        if initial:
            payload.update(tools=[TOOL], tool_choice="auto")
        raw = self._request(candidate.endpoint, candidate.provider, "/v1/chat/completions", payload)
        turn = self.parse(raw)
        try:
            reasoning = strict_json(raw)["choices"][0]["message"].get("reasoning")
            separated = isinstance(reasoning, str) and bool(reasoning.strip())
        except (ValueError, KeyError, IndexError, TypeError, UnicodeError):
            raise CognitionError("VALIDATION_RESPONSE_INVALID") from None
        return turn, separated


class OfferingValidator:
    def __init__(self, candidate, observer, transport, *, clock=utcnow):
        self.candidate, self.observer, self.transport, self.clock = candidate, observer, transport, clock
        self.run_id = str(uuid4())
        self.revision = "cfv-" + self.run_id
        self.report = {"schema": SUITE, "run_id": self.run_id, "status": "INCOMPLETE",
            "source_catalog_digest": candidate.source_digest, "source_catalog_revision": candidate.source_revision,
            "selection": asdict(candidate.selection(self.revision)), "checks": [], "invocations": []}
        self.catalog = None
        self.used = False

    def evaluate(self, *, context, authority, guard, record, admission=nullcontext):
        require(not self.used, "VALIDATION_ALREADY_RUN")
        self.used = True
        started, monotonic_start = self.clock(), time.monotonic()
        self.report.update(started_at=iso(started), mission_id=context.mission_id, agent_id=context.agent_id,
            work_item_id=context.work_item_id, attempt_id=context.attempt_id, grant_id=context.delegation_id,
            correlation_id=context.correlation_id)

        def current():
            require(0 <= (self.clock() - started).total_seconds() <= 300
                    and time.monotonic() - monotonic_start <= 300, "VALIDATION_DEADLINE")
            guard()

        def observe():
            # Metadata I/O is bounded but can outlive a grant or Runtime assignment.
            current()
            value = self.observer.observe(self.candidate)
            require(started <= timestamp(value["observed_at"]) <= self.clock()
                    and (self.clock() - timestamp(value["observed_at"])).total_seconds() <= 30,
                    "VALIDATION_OBSERVATION_STALE")
            self.transport.version(self.candidate)
            require(self.transport.available(self.candidate.endpoint, self.candidate.provider, self.candidate.offering),
                    "VALIDATION_DISCOVERY_FAILED")
            return value

        try:
            self.transport.validate_configuration(self.candidate.endpoint, self.candidate.provider)
            before = observe()
            self.report["checks"].append("deployment_and_discovery")
            messages = [{"role": "system", "content": "This is a synthetic protocol conformance test. "
                "You must first call lookup_validation_value exactly once with key cfv_probe. "
                "Do not invent the value. After its result, reply with only the value, no punctuation or explanation."},
                {"role": "user", "content": "What is the value of cfv_probe? Use the lookup tool."}]
            nonce = "CFV-" + uuid4().hex
            for ordinal in (1, 2):
                # Never reuse eligibility across metadata I/O or the previous response.
                current()
                facts = CognitionInvocationFacts(digest({"suite": SUITE}), self.candidate.selection(self.revision),
                    self.candidate.offering.model_id, ordinal, 1,
                    digest({"messages": messages, "tools": [TOOL] if ordinal == 1 else [], "suite": SUITE}),
                    recorded_at=iso(self.clock()))
                with admission():
                    decision = authority.authorize(context, facts)
                    facts = replace(facts, **asdict(decision))
                    record(facts)
                    current()  # refresh Aquila and Runtime after authorization, at admission
                call_start = time.monotonic()
                try:
                    turn, separated = self.transport.probe(self.candidate, messages, initial=ordinal == 1)
                    if ordinal == 1:
                        require(separated, "VALIDATION_REASONING_NOT_SEPARATED")
                        require(turn.finish_reason == "tool_calls" and not turn.content and len(turn.tool_calls) == 1,
                                "VALIDATION_TOOL_SHAPE")
                        call = turn.tool_calls[0]
                        require(call.name == "lookup_validation_value"
                                and strict_json(call.arguments_json) == {"key": "cfv_probe"}, "VALIDATION_TOOL_ARGUMENTS")
                        messages += [{"role": "assistant", "content": None, "tool_calls": [{"id": call.call_id,
                            "type": "function", "function": {"name": call.name, "arguments": call.arguments_json}}]},
                            {"role": "tool", "tool_call_id": call.call_id, "content": json.dumps({"value": nonce})}]
                        self.report["checks"].extend(("separate_reasoning_field", "typed_single_tool_call"))
                    else:
                        require(turn.finish_reason == "stop" and not turn.tool_calls
                                and turn.content is not None and turn.content.strip() == nonce, "VALIDATION_CONTINUATION")
                        self.report["checks"].append("matching_tool_continuation")
                    # Do not persist provider-controlled IDs, text, tool arguments or reasoning.
                    facts = replace(facts, status="SUCCESS", finish_reason=turn.finish_reason,
                        response_digest=digest(asdict(turn)), prompt_tokens=turn.prompt_tokens,
                        completion_tokens=turn.completion_tokens, reasoning_tokens=turn.reasoning_tokens)
                except (CognitionError, ValueError, TypeError, UnicodeError) as exc:
                    code = exc.code if isinstance(exc, CognitionError) else "VALIDATION_RESPONSE_INVALID"
                    facts = replace(facts, status="FAILED", error_code=code)
                    authority.record_outcome(context, facts)
                    record(facts)
                    self.report["invocations"].append(asdict(facts))
                    raise CognitionError(code) from None
                facts = replace(facts, latency_ms=min(int((time.monotonic() - call_start) * 1000), 2**31 - 1))
                authority.record_outcome(context, facts)
                record(facts)
                self.report["invocations"].append(asdict(facts))
                # In-flight cancellation/revocation must not permit continuation or a report.
                current()
            after = observe()
            require(before["identity"] == after["identity"], "VALIDATION_DEPLOYMENT_CHANGED")
            # Final observation can also race authority; probe success alone cannot publish.
            current()
            completed = self.clock()
            self.report.update(status="PROBES_PASSED", completed_at=iso(completed),
                deployment_before=before, deployment_after=after,
                code_sha256={name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                             for name in ("offering_validation.py", "deployment_observation.py")})
            self.report["checks"].append("deployment_unchanged")
            self.catalog = self.candidate.validated_catalog(self.revision, completed)
            self.report["catalog_digest"] = digest(self.catalog)
            return self.report
        except Exception as exc:
            self.catalog = None
            self.report.update(status="FAIL", error_code=exc.code if isinstance(exc, CognitionError) else "VALIDATION_FAILED")
            raise CognitionError(self.report["error_code"]) from None


class ValidationBundle:
    """Fresh private directory; catalog name becomes visible only after evidence."""

    def __init__(self, root):
        self.root = Path(root).absolute()
        require(self.root == self.root.resolve() and self.root.parent.is_dir(), "VALIDATION_OUTPUT_UNSAFE")
        try:
            self.root.mkdir(mode=0o700)
            self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:
            raise CognitionError("VALIDATION_OUTPUT_OCCUPIED_OR_UNSAFE") from None

    def close(self):
        os.close(self.fd)

    def write(self, name, value):
        require(name in {"report.json", "failure.json", ".catalog.pending"}, "VALIDATION_OUTPUT_NAME")
        info = os.fstat(self.fd)
        require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                "VALIDATION_OUTPUT_UNSAFE")
        data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(data) <= 65536, "VALIDATION_REPORT_TOO_LARGE")
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        with os.fdopen(fd, "wb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        os.fsync(self.fd)

    def publish(self, validator, *, accepted_result, guard):
        require(validator.report["status"] == "PROBES_PASSED" and validator.catalog is not None,
                "VALIDATION_NOT_PASSED")
        completed = timestamp(validator.report["completed_at"])
        def current():
            require(0 <= (validator.clock() - completed).total_seconds() <= 60, "VALIDATION_PUBLICATION_STALE")
            guard()
        require(digest(validator.catalog) == validator.report["catalog_digest"], "VALIDATION_ARTIFACT_MISMATCH")
        current()
        identifier(accepted_result.result_id)
        require(accepted_result.work_item_id == validator.report["work_item_id"]
                and accepted_result.attempt_id == validator.report["attempt_id"], "VALIDATION_RESULT_MISMATCH")
        # This immutable report attests probes/accepted work, not publication. Only
        # catalog.json is the commit marker; an interrupted report never claims PASS.
        report = {**validator.report, "status": "PROBES_PASSED", "accepted_result_id": accepted_result.result_id,
                  "accepted_result_digest": accepted_result.content_digest,
                  "publication_commit_marker": "catalog.json"}
        self.write("report.json", report)
        self.write(".catalog.pending", validator.catalog)
        current()
        # link is atomic and refuses an occupied destination; unlike replace it never overwrites.
        os.link(".catalog.pending", "catalog.json", src_dir_fd=self.fd, dst_dir_fd=self.fd, follow_symlinks=False)
        try:
            os.fsync(self.fd)
        except OSError:
            # Only withdraw our own new link, never an occupied/replaced user file.
            pending = os.stat(".catalog.pending", dir_fd=self.fd, follow_symlinks=False)
            final = os.stat("catalog.json", dir_fd=self.fd, follow_symlinks=False)
            if (pending.st_dev, pending.st_ino) == (final.st_dev, final.st_ino):
                os.unlink("catalog.json", dir_fd=self.fd)
            raise
        os.unlink(".catalog.pending", dir_fd=self.fd)
        return self.root / "catalog.json"
