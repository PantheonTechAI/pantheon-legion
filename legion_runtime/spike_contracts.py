"""Explicitly bounded, safe experimental facts; no Strands domain dependency."""

from dataclasses import dataclass, fields
from datetime import datetime

from legion_cognition.authorized import CognitionInvocationFacts
from legion_cognition.capability import CognitionSelection
from .work import _bounded, _positive, _timestamp, _uuid

SPIKE_CAPABILITIES = ("experimental_cognition", "model_reasoning", "tabula_corpus_read", "fixture_effect")


@dataclass(frozen=True)
class SpikeInvocationFacts(CognitionInvocationFacts):
    def __post_init__(self):
        if type(self.turn_ordinal) is not int or not 1 <= self.turn_ordinal <= 8:
            raise ValueError("INVALID_SPIKE_TURN_ORDINAL")
        # Reuse every accepted fact constraint except the explicitly separate
        # experimental turn range. The recorded ordinal is never rewritten.
        normalized = {field.name: getattr(self, field.name) for field in fields(CognitionInvocationFacts)}
        normalized["turn_ordinal"] = 1
        CognitionInvocationFacts(**normalized)


@dataclass(frozen=True)
class SpikeTrial:
    work_item_id: str
    active_attempt_id: str
    execution_id: str
    logical_operation_id: str
    trace_id: str
    config_digest: str
    mode: str
    persistence: str
    selection: dict
    version: int
    attempts_started: int
    model_calls: int
    retrievals: int
    input_reserved: int
    output_reserved: int
    deadline: str
    created_at: str

    def __post_init__(self):
        for name in ("work_item_id", "active_attempt_id", "execution_id", "logical_operation_id"):
            _uuid(getattr(self, name), name)
        if len(self.trace_id) != 32 or any(c not in "0123456789abcdef" for c in self.trace_id):
            raise ValueError("INVALID_TRACE_ID")
        if len(self.config_digest) != 64 or any(c not in "0123456789abcdef" for c in self.config_digest):
            raise ValueError("INVALID_CONFIG_DIGEST")
        if self.mode not in {"single", "graph", "swarm"} or self.persistence not in {"P0", "P1", "P2"}:
            raise ValueError("INVALID_SPIKE_PROFILE")
        CognitionSelection(**self.selection)
        _positive(self.version, "version")
        for key, maximum in (("attempts_started", 4), ("model_calls", 8), ("retrievals", 4),
                             ("output_reserved", 16384), ("input_reserved", 2**31 - 1)):
            value = getattr(self, key)
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError("SPIKE_BUDGET_EXCEEDED")
        if self.attempts_started == 0:
            raise ValueError("INVALID_ATTEMPT_COUNT")
        _timestamp(self.deadline, "deadline")
        _timestamp(self.created_at, "created_at")
        if datetime.fromisoformat(self.deadline) <= datetime.fromisoformat(self.created_at):
            raise ValueError("INVALID_DEADLINE")


@dataclass(frozen=True)
class SpikeOperation:
    operation_id: str
    work_item_id: str
    attempt_id: str
    execution_id: str
    kind: str
    ordinal: int
    status: str
    request_digest: str
    facts: dict
    recorded_at: str

    def __post_init__(self):
        for key in ("operation_id", "work_item_id", "attempt_id", "execution_id"):
            _uuid(getattr(self, key), key)
        if self.kind not in {"MODEL", "RETRIEVAL", "ACTION", "SESSION"}:
            raise ValueError("INVALID_SPIKE_OPERATION")
        if self.status not in {"PREPARED", "SUCCESS", "FAILED", "UNKNOWN"}:
            raise ValueError("INVALID_SPIKE_STATUS")
        if type(self.ordinal) is not int or not 1 <= self.ordinal <= 32:
            raise ValueError("INVALID_SPIKE_ORDINAL")
        if len(self.request_digest) != 64 or any(c not in "0123456789abcdef" for c in self.request_digest):
            raise ValueError("INVALID_REQUEST_DIGEST")
        _timestamp(self.recorded_at, "recorded_at")
        if not isinstance(self.facts, dict):
            raise ValueError("INVALID_SPIKE_FACTS")
        if self.kind == "MODEL":
            values = dict(self.facts)
            values["selection"] = CognitionSelection(**values["selection"])
            SpikeInvocationFacts(**values)
        else:
            allowed = {"decision_ids", "policy_versions", "scope_binding_id", "scope_binding_version",
                       "tabula_audit_correlation_id", "reference_ids", "error_code", "logical_operation_id",
                       "action_id", "permit_id", "receipt_id", "snapshot_digest", "snapshot_generation"}
            if set(self.facts) - allowed:
                raise ValueError("UNSAFE_SPIKE_FACT_FIELD")
            for key, value in self.facts.items():
                if isinstance(value, list):
                    if key not in {"decision_ids", "policy_versions", "reference_ids"} or len(value) > 8:
                        raise ValueError("INVALID_SPIKE_FACT_LIST")
                    for item in value:
                        _bounded(item, key, 1, 512)
                elif key == "snapshot_generation":
                    _positive(value, key)
                else:
                    _bounded(value, key, 1, 512)
