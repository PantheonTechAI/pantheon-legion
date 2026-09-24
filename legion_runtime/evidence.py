"""Consumer-owned contracts for bounded grounded evidence reads."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from legion_kernel import Principal

from .work import EvidenceCheckpointInvalid, WorkEvidenceReference, _bounded, _timestamp, _utf8_bounded, _uuid


MAX_EVIDENCE_RECORDS = 8
MAX_EVIDENCE_RECORD_BYTES = 8 * 1024
MAX_EVIDENCE_TOTAL_BYTES = 32 * 1024


class EvidenceReadError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class GroundedEvidenceReadRequest:
    organization_id: str
    workspace_id: str
    mission_id: str
    agent_id: str
    assignment_id: str
    workload: Principal
    delegation_id: str
    work_item_id: str
    attempt_id: str
    query: str
    correlation_id: str

    def __post_init__(self) -> None:
        for name in (
            "organization_id",
            "workspace_id",
            "mission_id",
            "agent_id",
            "assignment_id",
            "work_item_id",
            "attempt_id",
            "correlation_id",
        ):
            _uuid(getattr(self, name), name)
        _bounded(self.delegation_id, "delegation_id", 1, 512)
        if not isinstance(self.query, str) or not self.query.strip() or len(self.query) > 2000:
            raise ValueError("query must contain 1..2000 characters")


@dataclass(frozen=True)
class GroundedEvidenceRecord:
    record_id: str
    revision: str
    canonical_uri: str
    content: str
    retrieved_at: str

    def __post_init__(self) -> None:
        _bounded(self.record_id, "record_id", 1, 512)
        _bounded(self.revision, "revision", 1, 256)
        _bounded(self.canonical_uri, "canonical_uri", 1, 2048)
        _utf8_bounded(self.content, "content", 1, MAX_EVIDENCE_RECORD_BYTES)
        _timestamp(self.retrieved_at, "retrieved_at")


@dataclass(frozen=True)
class GroundedEvidenceBundle:
    authorization_decision_ids: tuple[str, ...]
    policy_versions: tuple[str, ...]
    successful_authorization_decision_id: str
    scope_binding_id: str
    scope_binding_version: str
    correlation_id: str
    tabula_audit_correlation_id: str
    retrieved_at: str
    records: tuple[GroundedEvidenceRecord, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.authorization_decision_ids) <= 4:
            raise ValueError("authorization decision IDs must contain 1..4 values")
        if len(self.policy_versions) != len(self.authorization_decision_ids):
            raise ValueError("policy versions must align with authorization decisions")
        if len(set(self.authorization_decision_ids)) != len(
            self.authorization_decision_ids
        ):
            raise ValueError("authorization decision IDs must be distinct")
        for value in self.authorization_decision_ids:
            _bounded(value, "authorization_decision_id", 1, 512)
        for value in self.policy_versions:
            _bounded(value, "policy_version", 1, 256)
        if self.successful_authorization_decision_id not in self.authorization_decision_ids:
            raise ValueError("successful decision must be in authorization decision IDs")
        _bounded(self.scope_binding_id, "scope_binding_id", 1, 512)
        _bounded(self.scope_binding_version, "scope_binding_version", 1, 256)
        _uuid(self.correlation_id, "correlation_id")
        _uuid(self.tabula_audit_correlation_id, "tabula_audit_correlation_id")
        _timestamp(self.retrieved_at, "retrieved_at")
        if not 1 <= len(self.records) <= MAX_EVIDENCE_RECORDS:
            raise ValueError("evidence records must contain 1..8 values")
        if sum(len(item.content.encode("utf-8")) for item in self.records) > MAX_EVIDENCE_TOTAL_BYTES:
            raise ValueError("evidence content exceeds aggregate limit")


class GroundedEvidenceReader(Protocol):
    def read(self, request: GroundedEvidenceReadRequest) -> GroundedEvidenceBundle: ...


class EvidenceAuthorityContext(Protocol):
    organization_id: str
    workspace_id: str
    mission_id: str
    agent_id: str
    assignment_id: str
    workload: Principal
    delegation_id: str
    work_item_id: str
    attempt_id: str
    correlation_id: str


@dataclass(frozen=True)
class GroundedEvidenceRereadRequest:
    organization_id: str
    workspace_id: str
    mission_id: str
    agent_id: str
    assignment_id: str
    workload: Principal
    delegation_id: str
    work_item_id: str
    attempt_id: str
    correlation_id: str
    references: tuple[WorkEvidenceReference, ...]

    def __post_init__(self):
        for name in ("organization_id", "workspace_id", "mission_id", "agent_id",
                     "assignment_id", "work_item_id", "attempt_id", "correlation_id"):
            _uuid(getattr(self, name), name)
        _bounded(self.delegation_id, "delegation_id", 1, 512)
        validate_recorded_references(self.work_item_id, self.references)


def validate_recorded_references(work_item_id, references):
    try:
        if (not isinstance(references, tuple) or not 1 <= len(references) <= 8
                or any(type(ref) is not WorkEvidenceReference for ref in references)
                or any(ref.work_item_id != work_item_id or ref.content_bytes is None
                       or ref.content_sha256 is None for ref in references)
                or len({ref.evidence_reference_id for ref in references}) != len(references)
                or len({ref.external_record_id for ref in references}) != len(references)
                or len({ref.attempt_id for ref in references}) != 1
                or len({(ref.scope_binding_id, ref.scope_binding_version) for ref in references}) != 1
                or sum(ref.content_bytes for ref in references) > MAX_EVIDENCE_TOTAL_BYTES):
            raise ValueError
        for ref in references:
            ref.__post_init__()
            _uuid(ref.scope_binding_id, "scope_binding_id")
            if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", ref.scope_binding_version):
                raise ValueError
            _bounded(ref.external_revision, "external_revision", 1, 128)
    except (ValueError, TypeError, AttributeError):
        raise EvidenceCheckpointInvalid() from None


class GroundedEvidenceRereader(Protocol):
    def reread(self, request: GroundedEvidenceRereadRequest) -> GroundedEvidenceBundle: ...
