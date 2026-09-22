"""In-process Aquila implementation of Legion Runtime's authority port."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlite3
from typing import Any, Callable
from uuid import uuid4

from legion_kernel import Principal
from legion_runtime.authority import (
    AuthorityDenied,
    AuthorityUnavailable,
    MissionAuthorityView,
)
from legion_runtime.agent import AgentIdentity
from legion_runtime.mission_context import AuthorizedMissionContext
from legion_runtime.evidence import GroundedEvidenceReadRequest
from legion_tabula.corpus import ScopeBinding
from legion_tabula.runtime_adapter import AuthorizedKnowledgeCredential

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


class InProcessAquilaCognitionAuthority:
    """Translate freshly persisted Aquila decisions; never invoke inference."""

    def __init__(self, service):
        self.service = service

    def authorize(self, context, facts):
        from legion_cognition.authorized import CognitionAuthorization
        from legion_cognition.capability import CognitionError
        try:
            response = self.service.authorize_cognition(context=context, facts=facts)
        except Exception:
            raise CognitionError("COGNITION_AUTHORITY_UNAVAILABLE", retryable=True) from None
        if response.status_code == 404:
            raise CognitionError("COGNITION_MISSION_NOT_FOUND")
        if response.status_code == 403:
            raise CognitionError("COGNITION_AUTHORITY_DENIED")
        if response.status_code != 200:
            raise CognitionError("COGNITION_AUTHORITY_UNAVAILABLE", retryable=True)
        try:
            return CognitionAuthorization(**response.body)
        except (ValueError, TypeError):
            raise CognitionError("COGNITION_AUTHORITY_INVALID") from None

    def record_outcome(self, context, facts):
        from legion_cognition.capability import CognitionError
        try:
            self.service.record_cognition_outcome(context=context, facts=facts)
        except Exception:
            raise CognitionError("COGNITION_AUDIT_UNAVAILABLE", ambiguous=True) from None


class InProcessAquilaKnowledgeAuthority:
    """Authorize each protected Tabula call and issue one fixture credential."""

    def __init__(
        self,
        service: AquilaService,
        credential_issuer: Callable[[dict[str, str]], str],
    ) -> None:
        self.service = service
        self.credential_issuer = credential_issuer

    def authorize_operation(
        self,
        request: GroundedEvidenceReadRequest,
        binding: ScopeBinding,
    ) -> AuthorizedKnowledgeCredential:
        try:
            response = self.service.authorize_grounded_knowledge_operation(
                workload=request.workload,
                mission_id=request.mission_id,
                delegation_id=request.delegation_id,
                binding=binding,
                work_item_id=request.work_item_id,
                attempt_id=request.attempt_id,
                correlation_id=request.correlation_id,
            )
        except (ConnectionError, OSError, TimeoutError, sqlite3.Error) as exc:
            raise AuthorityUnavailable() from exc
        if response.status_code in {403, 404, 409}:
            raise AuthorityDenied(str(response.body.get("code", "AUTHORITY_DENIED")))
        if response.status_code != 200:
            raise AuthorityUnavailable("AUTHORITY_RESPONSE_UNAVAILABLE")
        body = response.body
        try:
            now = datetime.now(timezone.utc)
            claims = {
                "schema_version": "1.0",
                "assertion_id": str(uuid4()),
                "issuer": "aquila",
                "audience": "pantheon-sts",
                "subject_id": request.workload.subject,
                "actor_id": "aquila",
                "mission_id": request.mission_id,
                "organization_id": request.organization_id,
                "workspace_id": request.workspace_id,
                "target_product": "TABULA",
                "target_audience": "pantheon-tabula-mcp",
                "operation": "TABULA_CORPUS_READ",
                "binding_id": binding.id,
                "binding_version": binding.version,
                "issued_at": now.isoformat().replace("+00:00", "Z"),
                "expires_at": (now + timedelta(minutes=5))
                .isoformat()
                .replace("+00:00", "Z"),
                "correlation_id": request.correlation_id,
            }
            token = self.credential_issuer(claims)
            if not isinstance(token, str) or not token:
                raise ValueError
            return AuthorizedKnowledgeCredential(
                decision_id=str(body["decision_id"]),
                policy_version=str(body["policy_version"]),
                invocation_id=str(body["invocation_id"]),
                token=token,
            )
        except (KeyError, TypeError, ValueError):
            raise AuthorityUnavailable("INVALID_AUTHORITY_RESPONSE") from None
        except Exception:
            raise AuthorityUnavailable("CREDENTIAL_ISSUANCE_UNAVAILABLE") from None

    def record_outcome(
        self,
        request: GroundedEvidenceReadRequest,
        binding: ScopeBinding,
        *,
        invocation_id: str,
        result: str,
        tabula_audit_correlation_id: str | None = None,
        record_references: tuple[dict[str, str], ...] = (),
        error_code: str | None = None,
        successful_authorization_decision_id: str | None = None,
    ) -> None:
        try:
            self.service.record_grounded_knowledge_outcome(
                workload=request.workload,
                mission_id=request.mission_id,
                invocation_id=invocation_id,
                correlation_id=request.correlation_id,
                result=result,
                binding=binding,
                tabula_audit_correlation_id=tabula_audit_correlation_id,
                record_references=record_references,
                error_code=error_code,
                work_item_id=request.work_item_id,
                attempt_id=request.attempt_id,
                successful_authorization_decision_id=(
                    successful_authorization_decision_id
                ),
            )
        except (ConnectionError, OSError, TimeoutError, sqlite3.Error) as exc:
            raise AuthorityUnavailable("AUTHORITY_AUDIT_UNAVAILABLE") from exc
