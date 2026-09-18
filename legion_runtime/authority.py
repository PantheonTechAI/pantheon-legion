"""Consumer-owned authority port for persistent Agent coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from legion_kernel import Principal

from .agent import AgentIdentity


@dataclass(frozen=True)
class MissionAuthorityView:
    mission_id: str
    organization_id: str
    workspace_id: str
    mission_status: str
    mission_version: int
    roe_revision: int
    decision_id: str
    policy_version: str
    evaluated_at: str


class AuthorityDenied(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AuthorityUnavailable(RuntimeError):
    def __init__(self, code: str = "AUTHORITY_UNAVAILABLE") -> None:
        super().__init__(code)
        self.code = code


class AquilaAgentAuthority(Protocol):
    def authorize_assignment(
        self,
        *,
        actor: Principal,
        agent: AgentIdentity,
        assignment_id: str,
        mission_id: str,
        correlation_id: str,
    ) -> MissionAuthorityView: ...

    def authorize_resume(
        self,
        *,
        workload: Principal,
        delegation_id: str,
        agent_id: str,
        assignment_id: str,
        mission_id: str,
        binding_id: str,
        correlation_id: str,
    ) -> MissionAuthorityView: ...
