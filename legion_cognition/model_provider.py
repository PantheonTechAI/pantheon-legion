"""Provider-neutral, auditable model boundary for read-only Scout work.

This module intentionally supplies no SDK, credentials, environment lookup, or
network client.  A deployment composes a provider implementation that keeps its
own credentials private and receives only the redacted Scout input below.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import re
from typing import Protocol
from uuid import uuid4

from .scout import MissionContext, ScoutEvidence


_SENSITIVE_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|authorization)\b\s*([:=])\s*\S+"
)
_BEARER_VALUE = re.compile(r"(?i)\bbearer\s+\S+")


@dataclass(frozen=True)
class ScoutInvocationPolicy:
    """Bounded provider behavior: 30 seconds per try and one timeout retry."""

    timeout_seconds: float = 30.0
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("MODEL_TIMEOUT_INVALID")
        if self.max_attempts < 1:
            raise ValueError("MODEL_MAX_ATTEMPTS_INVALID")


@dataclass(frozen=True)
class ModelInvocationRequest:
    """The complete, redacted input a provider is permitted to receive."""

    invocation_id: str
    context: MissionContext
    query: str
    evidence: tuple[ScoutEvidence, ...]
    timeout_seconds: float
    attempt: int


@dataclass(frozen=True)
class ModelInvocationResponse:
    """A provider response with stable provenance, but no provider credentials."""

    recommendation: str
    provider: str
    model: str
    response_id: str

    def __post_init__(self) -> None:
        if not self.recommendation.strip():
            raise ValueError("SCOUT_RESPONSE_INVALID")
        if not self.provider or not self.model or not self.response_id:
            raise ValueError("MODEL_RESPONSE_PROVENANCE_REQUIRED")


@dataclass(frozen=True)
class ModelInvocationProvenance:
    """Audit-safe provenance: hashes, never raw prompt, evidence, or response."""

    invocation_id: str
    provider: str
    model: str
    response_id: str | None
    attempts: int
    timeout_seconds: float
    request_digest: str
    response_digest: str | None
    error_code: str | None = None


@dataclass(frozen=True)
class ModelRecommendation:
    """Recommendation plus the provenance Aquila must append to the timeline."""

    recommendation: str
    provenance: ModelInvocationProvenance


class ModelProvider(Protocol):
    """Injected provider transport; its credentials remain outside this contract."""

    def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResponse: ...


class ModelProviderTimeout(TimeoutError):
    """A provider-recognized timeout that is eligible for the bounded retry."""


class ModelInvocationError(RuntimeError):
    """A failed call with audit-safe provenance for Aquila to record."""

    def __init__(self, error_code: str, provenance: ModelInvocationProvenance) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.provenance = provenance


class ScoutInputRedactor:
    """Remove common secret-bearing strings before a provider sees Scout input."""

    def redact(
        self,
        *,
        context: MissionContext,
        query: str,
        evidence: tuple[ScoutEvidence, ...],
    ) -> tuple[MissionContext, str, tuple[ScoutEvidence, ...]]:
        return (
            replace(
                context,
                title=self._redact_text(context.title),
                objective=self._redact_text(context.objective),
                constraints=tuple(self._redact_text(item) for item in context.constraints),
            ),
            self._redact_text(query),
            tuple(
                replace(item, source=self._redact_text(item.source), summary=self._redact_text(item.summary))
                for item in evidence
            ),
        )

    @staticmethod
    def _redact_text(value: str) -> str:
        value = _BEARER_VALUE.sub("Bearer [REDACTED]", value)
        return _SENSITIVE_VALUE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value)


class ModelProviderScoutResponder:
    """Adapt a provider transport to the LangGraph Scout responder seam.

    The adapter retries only explicit provider timeouts.  Other failures are
    surfaced immediately and all outcomes carry redacted, digest-only audit
    provenance.  A concrete provider must enforce ``timeout_seconds`` itself.
    """

    def __init__(
        self,
        provider: ModelProvider,
        *,
        policy: ScoutInvocationPolicy = ScoutInvocationPolicy(),
        redactor: ScoutInputRedactor | None = None,
    ) -> None:
        self._provider = provider
        self._policy = policy
        self._redactor = redactor or ScoutInputRedactor()

    def recommend(
        self,
        *,
        context: MissionContext,
        query: str,
        evidence: tuple[ScoutEvidence, ...],
    ) -> ModelRecommendation:
        redacted_context, redacted_query, redacted_evidence = self._redactor.redact(
            context=context, query=query, evidence=evidence
        )
        invocation_id = str(uuid4())
        request_digest = _request_digest(redacted_context, redacted_query, redacted_evidence)
        for attempt in range(1, self._policy.max_attempts + 1):
            request = ModelInvocationRequest(
                invocation_id=invocation_id,
                context=redacted_context,
                query=redacted_query,
                evidence=redacted_evidence,
                timeout_seconds=self._policy.timeout_seconds,
                attempt=attempt,
            )
            try:
                response = self._provider.invoke(request)
            except ModelProviderTimeout:
                if attempt < self._policy.max_attempts:
                    continue
                raise ModelInvocationError(
                    "MODEL_TIMEOUT",
                    _failure_provenance(
                        invocation_id, attempt, self._policy.timeout_seconds, request_digest, "MODEL_TIMEOUT"
                    ),
                ) from None
            except Exception as exc:
                raise ModelInvocationError(
                    "MODEL_PROVIDER_FAILED",
                    _failure_provenance(
                        invocation_id, attempt, self._policy.timeout_seconds, request_digest, "MODEL_PROVIDER_FAILED"
                    ),
                ) from exc
            return ModelRecommendation(
                recommendation=response.recommendation,
                provenance=ModelInvocationProvenance(
                    invocation_id=invocation_id,
                    provider=response.provider,
                    model=response.model,
                    response_id=response.response_id,
                    attempts=attempt,
                    timeout_seconds=self._policy.timeout_seconds,
                    request_digest=request_digest,
                    response_digest=_digest(response.recommendation),
                ),
            )
        raise AssertionError("unreachable")


def _failure_provenance(
    invocation_id: str, attempts: int, timeout_seconds: float, request_digest: str, error_code: str
) -> ModelInvocationProvenance:
    return ModelInvocationProvenance(
        invocation_id=invocation_id,
        provider="UNRESOLVED",
        model="UNRESOLVED",
        response_id=None,
        attempts=attempts,
        timeout_seconds=timeout_seconds,
        request_digest=request_digest,
        response_digest=None,
        error_code=error_code,
    )


def _request_digest(context: MissionContext, query: str, evidence: tuple[ScoutEvidence, ...]) -> str:
    return _digest(
        json.dumps(
            {
                "context": {
                    "mission_id": context.mission_id,
                    "mission_version": context.mission_version,
                    "title": context.title,
                    "objective": context.objective,
                    "status": context.status,
                    "roe_level": context.roe_level,
                    "constraints": context.constraints,
                },
                "query": query,
                "evidence": [item.__dict__ for item in evidence],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
