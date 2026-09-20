"""Provider-neutral cognition contract for persistent Agent work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .agent import AgentRole
from .work import _bounded, _timestamp, _utf8_bounded, _uuid


@dataclass(frozen=True)
class AgentEvidence:
    reference_id: str
    record_id: str
    revision: str
    canonical_uri: str
    content: str
    retrieved_at: str

    def __post_init__(self) -> None:
        _uuid(self.reference_id, "reference_id")
        _bounded(self.record_id, "record_id", 1, 512)
        _bounded(self.revision, "revision", 1, 256)
        _bounded(self.canonical_uri, "canonical_uri", 1, 2048)
        _utf8_bounded(self.content, "content", 1, 8 * 1024)
        _timestamp(self.retrieved_at, "retrieved_at")


@dataclass(frozen=True)
class AgentMissionContext:
    mission_id: str
    mission_version: int
    status: str
    title: str
    objective: str
    roe_level: str
    constraints: tuple[str, ...]


@dataclass(frozen=True)
class AgentCognitionRequest:
    request_id: str
    agent_id: str
    agent_role: AgentRole
    workload_subject: str
    work_item_id: str
    attempt_id: str
    mission_id: str
    mission_version: int
    logical_capability: str
    objective: str
    required_capabilities: tuple[str, ...]
    context: AgentMissionContext
    evidence: tuple[AgentEvidence, ...] = ()

    def __post_init__(self) -> None:
        if len(self.evidence) > 8:
            raise ValueError("evidence must contain at most 8 values")
        reference_ids = tuple(item.reference_id for item in self.evidence)
        if len(set(reference_ids)) != len(reference_ids):
            raise ValueError("evidence reference IDs must be distinct")
        if sum(len(item.content.encode("utf-8")) for item in self.evidence) > 32 * 1024:
            raise ValueError("evidence content exceeds aggregate limit")


@dataclass(frozen=True)
class AgentCognitionResult:
    request_id: str
    agent_id: str
    work_item_id: str
    attempt_id: str
    mission_id: str
    mission_version: int
    summary: str
    evidence_references: tuple[str, ...] = ()


class CognitionUnavailable(RuntimeError):
    def __init__(self, code: str = "COGNITION_UNAVAILABLE") -> None:
        super().__init__(code)
        self.code = code


class CognitionRejected(RuntimeError):
    def __init__(self, code: str = "COGNITION_RESULT_INVALID") -> None:
        super().__init__(code)
        self.code = code


class ReadOnlyCognition(Protocol):
    def run(self, request: AgentCognitionRequest) -> AgentCognitionResult: ...
