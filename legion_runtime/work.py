"""Durable Runtime-owned coordination records for bounded Agent work."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from uuid import UUID


class WorkStatus(str, Enum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    RETRYABLE = "RETRYABLE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AttemptStatus(str, Enum):
    PREPARED = "PREPARED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class WorkKind(str, Enum):
    READ_ONLY_ANALYSIS = "READ_ONLY_ANALYSIS"
    GROUNDED_CORPUS_ANALYSIS = "GROUNDED_CORPUS_ANALYSIS"
    TOOL_ASSISTED_CORPUS_ANALYSIS = "TOOL_ASSISTED_CORPUS_ANALYSIS"


class AttemptStage(str, Enum):
    MISSION_CONTEXT = "MISSION_CONTEXT"
    EVIDENCE_RETRIEVAL = "EVIDENCE_RETRIEVAL"
    COGNITION = "COGNITION"
    COGNITION_SELECTION = "COGNITION_SELECTION"
    COGNITION_INITIAL = "COGNITION_INITIAL"
    TOOL_REQUESTED = "TOOL_REQUESTED"
    COGNITION_CONTINUATION = "COGNITION_CONTINUATION"


class EvidenceSourceType(str, Enum):
    TABULA_CORPUS = "TABULA_CORPUS"


@dataclass(frozen=True)
class WorkItem:
    work_item_id: str
    mission_id: str
    centurion_agent_id: str
    centurion_assignment_id: str
    scout_agent_id: str
    scout_assignment_id: str
    objective: str
    required_capabilities: tuple[str, ...]
    status: WorkStatus
    version: int
    correlation_id: str
    causation_id: str | None
    created_at: str
    updated_at: str
    cancelled_at: str | None = None
    cancellation_reason: str | None = None
    kind: WorkKind = WorkKind.READ_ONLY_ANALYSIS

    def __post_init__(self) -> None:
        for name in (
            "work_item_id",
            "mission_id",
            "centurion_agent_id",
            "centurion_assignment_id",
            "scout_agent_id",
            "scout_assignment_id",
            "correlation_id",
        ):
            _uuid(getattr(self, name), name)
        _utf8_bounded(self.objective, "objective", 1, 4096)
        if not isinstance(self.required_capabilities, tuple):
            raise TypeError("required_capabilities must be a tuple")
        if not 1 <= len(self.required_capabilities) <= 16:
            raise ValueError("required_capabilities must contain 1..16 values")
        for capability in self.required_capabilities:
            _bounded(capability, "required capability", 1, 128)
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("required_capabilities must be distinct")
        _positive(self.version, "version")
        _optional_bounded(self.causation_id, "causation_id", 512)
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")
        if self.cancelled_at is not None:
            _timestamp(self.cancelled_at, "cancelled_at")
        _optional_utf8_bounded(
            self.cancellation_reason, "cancellation_reason", 1024
        )
        if self.status == WorkStatus.CANCELLED:
            if self.cancelled_at is None or self.cancellation_reason is None:
                raise ValueError("cancelled work requires cancellation provenance")
        elif self.cancelled_at is not None or self.cancellation_reason is not None:
            raise ValueError("non-cancelled work cannot have cancellation provenance")
        profiles = {
            WorkKind.READ_ONLY_ANALYSIS: ("read_only_analysis",),
            WorkKind.GROUNDED_CORPUS_ANALYSIS: ("read_only_analysis", "tabula_corpus_read"),
            WorkKind.TOOL_ASSISTED_CORPUS_ANALYSIS: ("read_only_analysis", "model_reasoning", "tabula_corpus_read"),
        }
        if self.kind not in profiles or self.required_capabilities != profiles[self.kind]:
            raise ValueError("work requires exact capabilities")
        if self.kind != WorkKind.READ_ONLY_ANALYSIS and len(self.objective) > 2000:
            raise ValueError("grounded objective exceeds Corpus query limit")


@dataclass(frozen=True)
class WorkAttempt:
    attempt_id: str
    work_item_id: str
    scout_agent_id: str
    scout_binding_id: str
    status: AttemptStatus
    attempt_number: int
    mission_version: int | None
    authorization_decision_id: str | None
    error_code: str | None
    version: int
    created_at: str
    updated_at: str
    attempt_stage: AttemptStage | None = None
    knowledge_authorization_decision_ids: tuple[str, ...] = ()
    successful_knowledge_decision_id: str | None = None
    evidence_correlation_id: str | None = None
    tabula_audit_correlation_id: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "attempt_id",
            "work_item_id",
            "scout_agent_id",
            "scout_binding_id",
        ):
            _uuid(getattr(self, name), name)
        _positive(self.attempt_number, "attempt_number")
        if self.mission_version is not None:
            _positive(self.mission_version, "mission_version")
        _optional_bounded(
            self.authorization_decision_id, "authorization_decision_id", 512
        )
        _optional_bounded(self.error_code, "error_code", 256)
        if not isinstance(self.knowledge_authorization_decision_ids, tuple):
            raise TypeError("knowledge_authorization_decision_ids must be a tuple")
        if len(self.knowledge_authorization_decision_ids) > 4:
            raise ValueError("knowledge authorization decision IDs exceed limit")
        for decision_id in self.knowledge_authorization_decision_ids:
            _bounded(decision_id, "knowledge authorization decision ID", 1, 512)
        if len(set(self.knowledge_authorization_decision_ids)) != len(
            self.knowledge_authorization_decision_ids
        ):
            raise ValueError("knowledge authorization decision IDs must be distinct")
        _optional_bounded(
            self.successful_knowledge_decision_id,
            "successful knowledge decision ID",
            512,
        )
        if (
            self.successful_knowledge_decision_id is not None
            and self.successful_knowledge_decision_id
            not in self.knowledge_authorization_decision_ids
        ):
            raise ValueError("successful knowledge decision must be in decision IDs")
        for value, name in (
            (self.evidence_correlation_id, "evidence_correlation_id"),
            (self.tabula_audit_correlation_id, "tabula_audit_correlation_id"),
        ):
            if value is not None:
                _uuid(value, name)
        _positive(self.version, "version")
        _timestamp(self.created_at, "created_at")
        _timestamp(self.updated_at, "updated_at")


@dataclass(frozen=True)
class WorkEvidenceReference:
    evidence_reference_id: str
    work_item_id: str
    attempt_id: str
    source_type: EvidenceSourceType
    external_record_id: str
    external_revision: str
    canonical_uri: str
    scope_binding_id: str
    scope_binding_version: str
    successful_authorization_decision_id: str
    tabula_audit_correlation_id: str
    retrieved_at: str
    created_at: str

    def __post_init__(self) -> None:
        for name in (
            "evidence_reference_id",
            "work_item_id",
            "attempt_id",
            "tabula_audit_correlation_id",
        ):
            _uuid(getattr(self, name), name)
        for value, name, maximum in (
            (self.external_record_id, "external_record_id", 512),
            (self.external_revision, "external_revision", 256),
            (self.canonical_uri, "canonical_uri", 2048),
            (self.scope_binding_id, "scope_binding_id", 512),
            (self.scope_binding_version, "scope_binding_version", 256),
            (
                self.successful_authorization_decision_id,
                "successful_authorization_decision_id",
                512,
            ),
        ):
            _bounded(value, name, 1, maximum)
        _timestamp(self.retrieved_at, "retrieved_at")
        _timestamp(self.created_at, "created_at")


@dataclass(frozen=True)
class WorkResult:
    result_id: str
    work_item_id: str
    attempt_id: str
    scout_agent_id: str
    scout_binding_id: str
    mission_version: int
    summary: str
    evidence_references: tuple[str, ...]
    content_digest: str
    produced_at: str

    def __post_init__(self) -> None:
        for name in (
            "result_id",
            "work_item_id",
            "attempt_id",
            "scout_agent_id",
            "scout_binding_id",
        ):
            _uuid(getattr(self, name), name)
        _positive(self.mission_version, "mission_version")
        _utf8_bounded(self.summary, "summary", 1, 8192)
        if not isinstance(self.evidence_references, tuple):
            raise TypeError("evidence_references must be a tuple")
        if len(self.evidence_references) > 32:
            raise ValueError("evidence_references must contain at most 32 values")
        for reference in self.evidence_references:
            _bounded(reference, "evidence reference", 1, 1024)
        if len(set(self.evidence_references)) != len(self.evidence_references):
            raise ValueError("evidence_references must be distinct")
        if (
            not isinstance(self.content_digest, str)
            or len(self.content_digest) != 64
            or any(character not in "0123456789abcdef" for character in self.content_digest)
        ):
            raise ValueError("content_digest must be a lowercase SHA-256 digest")
        if self.content_digest != result_digest(
            self.summary, self.evidence_references
        ):
            raise ValueError("content_digest does not match result content")
        _timestamp(self.produced_at, "produced_at")


def result_digest(summary: str, evidence_references: tuple[str, ...]) -> str:
    payload = json.dumps(
        {"evidence_references": evidence_references, "summary": summary},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _uuid(value: str, name: str) -> None:
    try:
        UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{name} must be a UUID") from exc


def _positive(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def _bounded(value: str, name: str, minimum: int, maximum: int) -> None:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValueError(f"{name} must contain {minimum}..{maximum} characters")


def _utf8_bounded(value: str, name: str, minimum: int, maximum: int) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    length = len(value.strip().encode("utf-8"))
    if not minimum <= length <= maximum:
        raise ValueError(f"{name} must contain {minimum}..{maximum} UTF-8 bytes")


def _optional_bounded(value: str | None, name: str, maximum: int) -> None:
    if value is not None:
        _bounded(value, name, 1, maximum)


def _optional_utf8_bounded(value: str | None, name: str, maximum: int) -> None:
    if value is not None:
        _utf8_bounded(value, name, 1, maximum)


def _timestamp(value: str, name: str) -> None:
    _bounded(value, name, 1, 64)
    if not value.endswith("Z"):
        raise ValueError(f"{name} must be a UTC timestamp")
