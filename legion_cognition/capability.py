"""Logical cognition requirements and static, capability-selected offerings."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable, Protocol

from legion_resource.inference import (
    InferenceEndpoint, InferenceTopologyCatalog, distinct_records, enabled_flag,
    identifier, observation, positive, timestamp,
)


def digest(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


class CognitionError(RuntimeError):
    def __init__(self, code="COGNITION_UNAVAILABLE", *, retryable=False, ambiguous=False):
        identifier(code)
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.ambiguous = ambiguous


@dataclass(frozen=True)
class CognitionRequirement:
    capability: str = "reasoning"
    minimum_context: int = 16384
    tool_calls: bool = True
    separated_reasoning: bool = True
    locality: str = "LOCAL_ONLY"
    data_classification: str = "internal"
    trust_zone: str = "homelab"

    def __post_init__(self):
        for value in (self.capability, self.data_classification, self.trust_zone):
            identifier(value)
        positive(self.minimum_context)
        enabled_flag(self.tool_calls)
        enabled_flag(self.separated_reasoning)
        if self.locality not in {"LOCAL_ONLY", "ANY"}:
            raise ValueError("INVALID_REQUIREMENT_LOCALITY")

    @property
    def requirement_id(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class InferenceProvider:
    provider_id: str
    endpoint_id: str
    adapter_type: str
    runtime_family: str
    runtime_version: str
    parser_profile: str
    api_prefix: str = "/v1"
    credential_reference: str | None = None
    enabled: bool = True

    def __post_init__(self):
        for value in (self.provider_id, self.endpoint_id, self.runtime_family,
                      self.runtime_version, self.parser_profile):
            identifier(value)
        if self.adapter_type != "openai-compatible" or self.api_prefix != "/v1":
            raise ValueError("UNSUPPORTED_PROVIDER_PROTOCOL")
        if self.credential_reference is not None:
            identifier(self.credential_reference)
        enabled_flag(self.enabled)


@dataclass(frozen=True)
class OfferingValidationRecord:
    provider_id: str
    runtime_family: str
    runtime_version: str
    model_id: str
    parser_profile: str
    features: tuple[str, ...]
    validated_at: str
    valid_until: str

    def __post_init__(self):
        for value in (self.provider_id, self.runtime_family, self.runtime_version,
                      self.model_id, self.parser_profile):
            identifier(value)
        feature_values(self.features)
        if timestamp(self.validated_at) >= timestamp(self.valid_until):
            raise ValueError("INVALID_VALIDATION_PERIOD")


def feature_values(values):
    if not isinstance(values, tuple) or not values or len(set(values)) != len(values):
        raise ValueError("INVALID_FEATURES")
    for value in values:
        identifier(value)


@dataclass(frozen=True)
class ModelOffering:
    offering_id: str
    provider_id: str
    model_id: str
    context_window: int
    features: tuple[str, ...]
    validation_record: OfferingValidationRecord
    priority: int = 100
    enabled: bool = True
    data_classifications: tuple[str, ...] = ("internal",)

    def __post_init__(self):
        for value in (self.offering_id, self.provider_id, self.model_id):
            identifier(value)
        positive(self.context_window)
        positive(self.priority)
        feature_values(self.features)
        feature_values(self.data_classifications)
        if not isinstance(self.validation_record, OfferingValidationRecord):
            raise ValueError("OFFERING_VALIDATION_REQUIRED")
        enabled_flag(self.enabled)


@dataclass(frozen=True)
class CognitionOfferingCatalog:
    catalog_revision: str
    providers: tuple[InferenceProvider, ...]
    offerings: tuple[ModelOffering, ...]

    def __post_init__(self):
        identifier(self.catalog_revision)
        distinct_records(self.providers, InferenceProvider, "provider_id")
        distinct_records(self.offerings, ModelOffering, "offering_id")
        if len({p.endpoint_id for p in self.providers}) != len(self.providers):
            raise ValueError("ONE_PROVIDER_PER_ENDPOINT_REQUIRED")
        for offering in self.offerings:
            self.resolve_provider(offering.provider_id)

    def resolve_provider(self, provider_id):
        for provider in self.providers:
            if provider.provider_id == provider_id:
                return provider
        raise ValueError("UNKNOWN_INFERENCE_PROVIDER")

    def resolve_offering(self, offering_id):
        for offering in self.offerings:
            if offering.offering_id == offering_id:
                return offering
        raise ValueError("UNKNOWN_MODEL_OFFERING")


@dataclass(frozen=True)
class CognitionSelection:
    catalog_revision: str
    offering_id: str
    provider_id: str
    endpoint_id: str
    node_id: str

    def __post_init__(self):
        for value in asdict(self).values():
            identifier(value)


@dataclass(frozen=True)
class OfferingObservation:
    offering_id: str
    metric: str
    value: float
    unit: str
    measured_at: str
    benchmark_note: str = ""

    def __post_init__(self):
        observation(self.offering_id, self.metric, self.value, self.unit, self.measured_at,
                    self.benchmark_note, {"model_available", "context_window", "ttft", "decode_throughput"})


class OfferingProbe(Protocol):
    def available(self, endpoint: InferenceEndpoint, provider: InferenceProvider,
                  offering: ModelOffering) -> bool: ...


class CognitionRouter:
    """Match one immutable graph. A retry cannot reroute a prior selection."""

    def __init__(self, resources: InferenceTopologyCatalog, cognition: CognitionOfferingCatalog,
                 probe: OfferingProbe, *, clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self.probe = probe
        self.clock = clock
        self._revisions = {}
        self.update_catalog(resources, cognition)

    def update_catalog(self, resources, cognition):
        if resources.catalog_revision != cognition.catalog_revision:
            raise ValueError("CATALOG_REVISION_MISMATCH")
        if {p.endpoint_id for p in cognition.providers} != {e.endpoint_id for e in resources.endpoints}:
            raise ValueError("CATALOG_ENDPOINT_PROVIDER_MISMATCH")
        for provider in cognition.providers:
            resources.resolve_endpoint(provider.endpoint_id)
        revision = resources.catalog_revision
        fingerprint = digest((asdict(resources), asdict(cognition)))
        if revision in self._revisions and self._revisions[revision] != fingerprint:
            raise ValueError("IMMUTABLE_CATALOG_REVISION")
        self._revisions[revision] = fingerprint
        self._catalogs = (resources, cognition)

    def _eligible(self, requirement, offering, provider, endpoint, node):
        record = offering.validation_record
        requested = {requirement.capability}
        if requirement.tool_calls:
            requested.add("tool_calls")
        if requirement.separated_reasoning:
            requested.add("separated_reasoning")
        return (all((offering.enabled, provider.enabled, endpoint.enabled, node.enabled))
                and offering.context_window >= requirement.minimum_context
                and requested.issubset(offering.features)
                and set(offering.features).issubset(record.features)
                and requirement.data_classification in offering.data_classifications
                and (requirement.locality != "LOCAL_ONLY" or node.locality == "LOCAL")
                and requirement.trust_zone == node.trust_zone
                and (record.provider_id, record.runtime_family, record.runtime_version,
                     record.model_id, record.parser_profile) ==
                    (provider.provider_id, provider.runtime_family, provider.runtime_version,
                     offering.model_id, provider.parser_profile)
                and timestamp(record.validated_at) <= self.clock() < timestamp(record.valid_until))

    def select(self, requirement: CognitionRequirement) -> CognitionSelection:
        resources, cognition = self._catalogs
        for offering in sorted(cognition.offerings, key=lambda o: (o.priority, o.offering_id)):
            provider = cognition.resolve_provider(offering.provider_id)
            endpoint = resources.resolve_endpoint(provider.endpoint_id)
            node = resources.resolve_node(endpoint.node_id)
            if self._eligible(requirement, offering, provider, endpoint, node):
                if self.probe.available(endpoint, provider, offering):
                    selection = CognitionSelection(resources.catalog_revision, offering.offering_id,
                                                   provider.provider_id, endpoint.endpoint_id, node.node_id)
                    self.resolve(selection, requirement)
                    return selection
        raise CognitionError("COGNITION_NO_MATCH")

    def resolve(self, selection: CognitionSelection, requirement: CognitionRequirement):
        resources, cognition = self._catalogs
        try:
            if selection.catalog_revision != resources.catalog_revision:
                raise ValueError
            offering = cognition.resolve_offering(selection.offering_id)
            provider = cognition.resolve_provider(offering.provider_id)
            endpoint = resources.resolve_endpoint(provider.endpoint_id)
            node = resources.resolve_node(endpoint.node_id)
            if ((provider.provider_id, endpoint.endpoint_id, node.node_id) !=
                    (selection.provider_id, selection.endpoint_id, selection.node_id)
                    or not self._eligible(requirement, offering, provider, endpoint, node)):
                raise ValueError
        except (ValueError, TypeError):
            raise CognitionError("COGNITION_SELECTION_STALE") from None
        return endpoint, provider, offering


@dataclass(frozen=True)
class RequestedToolCall:
    call_id: str
    name: str
    arguments_json: str

    def __post_init__(self):
        identifier(self.call_id)
        identifier(self.name)
        if not isinstance(self.arguments_json, str) or len(self.arguments_json.encode("utf-8")) > 16384:
            raise ValueError("INVALID_TOOL_ARGUMENTS")


@dataclass(frozen=True)
class CognitionTurnResult:
    response_id: str
    finish_reason: str
    content: str | None = None
    tool_calls: tuple[RequestedToolCall, ...] = ()
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0

    def __post_init__(self):
        identifier(self.response_id)
        for count in (self.prompt_tokens, self.completion_tokens, self.reasoning_tokens):
            if type(count) is not int or not 0 <= count <= 2**31 - 1:
                raise ValueError("INVALID_PROVIDER_USAGE")
        if not isinstance(self.tool_calls, tuple) or len(self.tool_calls) > 8:
            raise ValueError("INVALID_TOOL_CALLS")
        if len({call.call_id for call in self.tool_calls}) != len(self.tool_calls):
            raise ValueError("DUPLICATE_TOOL_CALL")
        if self.tool_calls:
            if self.content not in {None, ""} or self.finish_reason != "tool_calls":
                raise ValueError("MIXED_PROVIDER_TURN")
        elif (self.finish_reason != "stop" or not isinstance(self.content, str)
              or not self.content.strip() or len(self.content.encode("utf-8")) > 8192):
            raise ValueError("INVALID_FINAL_CONTENT")
