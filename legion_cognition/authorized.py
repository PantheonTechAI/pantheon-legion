"""Cognition consumer authority port and one bounded, freshly authorized retry."""

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import time
from typing import Protocol

from legion_kernel import Principal
from legion_resource.inference import identifier, timestamp
from .capability import CognitionError, CognitionRequirement, CognitionSelection, digest


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CognitionInvocationContext:
    workload: Principal
    delegation_id: str
    mission_id: str
    agent_id: str
    assignment_id: str
    work_item_id: str
    attempt_id: str
    correlation_id: str

    def __post_init__(self):
        for key, value in self.__dict__.items():
            if key != "workload":
                identifier(value)


@dataclass(frozen=True)
class CognitionAuthorization:
    decision_id: str
    policy_version: str
    invocation_id: str

    def __post_init__(self):
        for value in asdict(self).values():
            identifier(value)


@dataclass(frozen=True)
class CognitionInvocationFacts:
    requirement_id: str
    selection: CognitionSelection
    model_id: str
    turn_ordinal: int
    transport_attempt_ordinal: int
    request_digest: str
    decision_id: str = "pending"
    policy_version: str = "pending"
    invocation_id: str = "pending"
    status: str = "PREPARED"
    response_id: str | None = None
    response_digest: str | None = None
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    latency_ms: int = 0
    error_code: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    argument_digest: str | None = None
    recorded_at: str = ""

    def __post_init__(self):
        for key in ("requirement_id", "model_id", "request_digest", "decision_id", "policy_version",
                    "invocation_id", "response_id", "response_digest", "error_code", "tool_name",
                    "tool_call_id", "argument_digest"):
            value = getattr(self, key)
            if value is not None:
                identifier(value)
        if (type(self.turn_ordinal) is not int or type(self.transport_attempt_ordinal) is not int
                or self.turn_ordinal not in {1, 2} or self.transport_attempt_ordinal not in {1, 2}):
            raise ValueError("INVALID_TURN_ORDINAL")
        if type(self.selection) is not CognitionSelection:
            raise ValueError("INVALID_COGNITION_SELECTION")
        timestamp(self.recorded_at)
        if self.status not in {"PREPARED", "SUCCESS", "FAILED"}:
            raise ValueError("INVALID_INVOCATION_STATUS")
        if self.finish_reason not in {None, "stop", "tool_calls"}:
            raise ValueError("INVALID_FINISH_REASON")
        for value in (self.prompt_tokens, self.completion_tokens, self.reasoning_tokens, self.latency_ms):
            if type(value) is not int or not 0 <= value < 2**31:
                raise ValueError("INVALID_INVOCATION_COUNT")


class CognitionAuthority(Protocol):
    def authorize(self, context: CognitionInvocationContext, facts: CognitionInvocationFacts) -> CognitionAuthorization: ...
    def record_outcome(self, context: CognitionInvocationContext, facts: CognitionInvocationFacts) -> None: ...


class AuthorizedCognitionInvoker:
    def __init__(self, router, transport, authority: CognitionAuthority):
        self.router = router
        self.transport = transport
        self.authority = authority

    def invoke(self, context, requirement: CognitionRequirement, selection, messages,
               *, turn_ordinal, tools=(), guard, record):
        for ordinal in (1, 2):
            guard()
            endpoint, provider, offering = self.router.resolve(selection, requirement)
            self.transport.validate_configuration(endpoint, provider)
            facts = CognitionInvocationFacts(requirement.requirement_id, selection, offering.model_id,
                                            turn_ordinal, ordinal, digest(messages), recorded_at=now())
            authorization = self.authority.authorize(context, facts)
            facts = replace(facts, **asdict(authorization))
            record(facts)
            guard()
            # Revalidate configuration after authorization; never silently reroute.
            endpoint, provider, offering = self.router.resolve(selection, requirement)
            started = time.monotonic()
            failure = None
            try:
                result = self.transport.chat(endpoint, provider, offering, messages, tools=tools)
            except CognitionError as exc:
                failure = exc
                facts = replace(facts, status="FAILED", error_code=exc.code)
            else:
                tool = result.tool_calls[0] if len(result.tool_calls) == 1 else None
                shape = {"response_id": result.response_id, "finish_reason": result.finish_reason,
                         "content_digest": digest(result.content), "tool_count": len(result.tool_calls)}
                facts = replace(facts, status="SUCCESS", response_id=result.response_id,
                                response_digest=digest(shape), finish_reason=result.finish_reason,
                                prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
                                reasoning_tokens=result.reasoning_tokens,
                                tool_name=tool.name if tool else None, tool_call_id=tool.call_id if tool else None,
                                argument_digest=digest(tool.arguments_json) if tool else None)
            facts = replace(facts, latency_ms=min(int((time.monotonic() - started) * 1000), 2**31 - 1),
                            recorded_at=now())
            # Failure here deliberately leaves the Runtime PREPARED fact ambiguous.
            self.authority.record_outcome(context, facts)
            record(facts)
            guard()
            if failure is None:
                return result
            if not failure.retryable or ordinal == 2:
                raise failure from None
        raise AssertionError("unreachable")
