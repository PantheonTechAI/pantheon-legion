"""In-process Aquila implementation of Legion Runtime's authority port."""

from __future__ import annotations

import sqlite3

from legion_kernel import Principal
from legion_runtime.authority import (
    AuthorityDenied,
    AuthorityUnavailable,
    MissionAuthorityView,
)
from legion_runtime.agent import AgentIdentity
from legion_runtime.mission_context import AuthorizedMissionContext

from .service import AquilaService


class InProcessAquilaAgentAuthority:
    """Translate Aquila's internal service responses into the Runtime port."""

    def __init__(self, service: AquilaService) -> None:
        self.service = service

    def authorize_assignment(
        self,
        *,
        actor: Principal,
        agent: AgentIdentity,
        assignment_id: str,
        mission_id: str,
        correlation_id: str,
    ) -> MissionAuthorityView:
        try:
            response = self.service.authorize_agent_assignment(
                actor=actor,
                mission_id=mission_id,
                agent_id=agent.agent_id,
                assignment_id=assignment_id,
                correlation_id=correlation_id,
            )
        except (ConnectionError, OSError, TimeoutError, sqlite3.Error) as exc:
            raise AuthorityUnavailable() from exc
        return self._view(response.status_code, response.body)

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
    ) -> MissionAuthorityView:
        try:
            response = self.service.authorize_agent_resume(
                workload=workload,
                delegation_id=delegation_id,
                agent_id=agent_id,
                assignment_id=assignment_id,
                mission_id=mission_id,
                binding_id=binding_id,
                correlation_id=correlation_id,
            )
        except (ConnectionError, OSError, TimeoutError, sqlite3.Error) as exc:
            raise AuthorityUnavailable() from exc
        return self._view(response.status_code, response.body)


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
    ) -> AuthorizedMissionContext:
        try:
            response = self.service.authorize_scout_context(
                workload=workload,
                delegation_id=delegation_id,
                agent_id=agent_id,
                assignment_id=assignment_id,
                work_item_id=work_item_id,
                attempt_id=attempt_id,
                mission_id=mission_id,
                correlation_id=correlation_id,
            )
        except (ConnectionError, OSError, TimeoutError, sqlite3.Error) as exc:
            raise AuthorityUnavailable() from exc
        if response.status_code == 200:
            body = response.body
            try:
                return AuthorizedMissionContext(
                    organization_id=str(body["organization_id"]),
                    workspace_id=str(body["workspace_id"]),
                    mission_id=str(body["mission_id"]),
                    mission_version=int(body["mission_version"]),
                    mission_status=str(body["mission_status"]),
                    title=str(body["title"]),
                    objective=str(body["objective"]),
                    roe_level=str(body["roe_level"]),
                    constraints=tuple(str(value) for value in body["constraints"]),
                    authorization_decision_id=str(body["decision_id"]),
                    policy_version=str(body["policy_version"]),
                    roe_revision=int(body["roe_revision"]),
                    evaluated_at=str(body["evaluated_at"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise AuthorityUnavailable("INVALID_AUTHORITY_RESPONSE") from exc
        if response.status_code in {403, 404, 409}:
            raise AuthorityDenied(
                str(response.body.get("code", "AUTHORITY_DENIED"))
            )
        raise AuthorityUnavailable("AUTHORITY_RESPONSE_UNAVAILABLE")
    @staticmethod
    def _view(status_code: int, body: dict[str, object]) -> MissionAuthorityView:
        if status_code == 200:
            try:
                return MissionAuthorityView(
                    mission_id=str(body["mission_id"]),
                    organization_id=str(body["organization_id"]),
                    workspace_id=str(body["workspace_id"]),
                    mission_status=str(body["mission_status"]),
                    mission_version=int(body["mission_version"]),
                    roe_revision=int(body["roe_revision"]),
                    decision_id=str(body["decision_id"]),
                    policy_version=str(body["policy_version"]),
                    evaluated_at=str(body["evaluated_at"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise AuthorityUnavailable("INVALID_AUTHORITY_RESPONSE") from exc
        if status_code in {403, 404, 409}:
            raise AuthorityDenied(str(body.get("code", "AUTHORITY_DENIED")))
        raise AuthorityUnavailable("AUTHORITY_RESPONSE_UNAVAILABLE")
