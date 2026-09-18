"""Provider-neutral cognition contract for persistent Agent work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .agent import AgentRole


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
