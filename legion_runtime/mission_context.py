"""Consumer-owned port for fresh Aquila-authorized Mission context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from legion_kernel import Principal


@dataclass(frozen=True)
class AuthorizedMissionContext:
    organization_id: str
    workspace_id: str
    mission_id: str
    mission_version: int
    mission_status: str
    title: str
    objective: str
    roe_level: str
    constraints: tuple[str, ...]
    authorization_decision_id: str
    policy_version: str
    roe_revision: int
    evaluated_at: str


class AquilaMissionContext(Protocol):
    def authorize_and_read(
        self,
        *,
        workload: Principal,
        delegation_id: str,
        agent_id: str,
        assignment_id: str,
        work_item_id: str,
        attempt_id: str,
        mission_id: str,
        correlation_id: str,
    ) -> AuthorizedMissionContext: ...
