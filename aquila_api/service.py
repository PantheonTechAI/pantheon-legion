"""HTTP-shaped Aquila operations without a web-framework dependency.

The service intentionally accepts authenticated ``Principal`` values rather
than parsing OIDC tokens. An HTTP adapter can perform authentication and call
these methods without changing Mission semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import UUID, uuid4

from legion_cognition import (
    CognitionRuntimeAdapter,
    MissionContext,
    ModelInvocationError,
    ModelInvocationProvenance,
    ScoutEvidence,
    ScoutRequest,
    ScoutResult,
)
from legion_fabrica import FabricaError, ToolExecutionAdapter, ToolInvocation, ToolResult
from legion_tabula import CorpusRead, CorpusReadError, KnowledgeScope, RegistryDiscovery, RegistryReadError, RetrievedKnowledge, ScopeBinding, TabulaCorpusClient, TabulaRegistryClient, TabulaRetrievalAdapter
from legion_kernel import (
    AuthorizationError,
    LegionKernel,
    MissionStatus,
    Principal,
    PrincipalType,
    RoeLevel,
    WorkerKilled,
)
from legion_runtime import DurableExecutionAdapter, ExecutionState, InMemoryDurableExecutionAdapter

from .authorization import AuthorizationEngine, AuthorizationRequest, Decision, DelegationGrant


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    body: dict[str, Any]
    headers: dict[str, str]


class AquilaService:
    """OpenAPI operation adapter backed by a Mission kernel instance."""

    def __init__(
        self,
        kernel: LegionKernel | None = None,
        authorization: AuthorizationEngine | None = None,
        execution: DurableExecutionAdapter | None = None,
    ) -> None:
        self.kernel = kernel or LegionKernel()
        self.authorization = authorization or AuthorizationEngine()
        self.execution = execution or InMemoryDurableExecutionAdapter()
        self.action_executions: dict[str, str] = {}
        self.delegations: dict[str, DelegationGrant] = {}

    def issue_delegation(
        self,
        *,
        issuer: Principal,
        subject: Principal,
        mission_id: str,
        allowed_operations: frozenset[str],
        roe_ceiling: RoeLevel,
        expires_at: str,
    ) -> str:
        """Issue one bounded workload grant under Mission-owner authority."""
        mission = self.kernel.get_mission(mission_id)
        if subject.type != PrincipalType.WORKLOAD:
            raise ValueError("DELEGATION_SUBJECT_MUST_BE_WORKLOAD")
        if not allowed_operations:
            raise ValueError("DELEGATION_OPERATIONS_REQUIRED")
        expires = _parse_timestamp(expires_at)
        if expires <= _parse_timestamp(self.authorization.clock()):
            raise ValueError("DELEGATION_EXPIRY_REQUIRED")
        decision = self.authorization.decide(
            AuthorizationRequest(
                principal=issuer,
                mission_id=mission_id,
                operation="ISSUE_DELEGATION",
                roe_level=mission.roe.level,
                mission_status=mission.status,
            )
        )
        if decision.decision == Decision.DENY:
            self.kernel.record_delegation_event(
                mission_id=mission_id, actor=issuer, event_type="DELEGATION_ISSUANCE_DENIED",
                result="DENY", grant_id="unissued", data={"reason": decision.reason},
            )
            raise AuthorizationError(decision.reason)
        grant = DelegationGrant(
            grant_id=str(uuid4()), issuer=issuer, subject=subject, mission_id=mission_id,
            allowed_operations=frozenset(allowed_operations), roe_ceiling=roe_ceiling,
            expires_at=expires_at, issued_at=decision.evaluated_at,
        )
        self.delegations[grant.grant_id] = grant
        self.kernel.record_delegation_event(
            mission_id=mission_id, actor=issuer, event_type="DELEGATION_ISSUED", result="SUCCESS",
            grant_id=grant.grant_id,
            data={"subject": subject.subject, "operations": sorted(grant.allowed_operations),
                  "roe_ceiling": roe_ceiling.value, "expires_at": expires_at,
                  "decision_id": decision.decision_id, "policy_version": decision.policy_version},
        )
        return grant.grant_id

    def revoke_delegation(
        self, *, actor: Principal, mission_id: str, delegation_id: str, reason: str
    ) -> None:
        """Revoke an issued grant; future workload uses fail closed."""
        mission = self.kernel.get_mission(mission_id)
        grant = self.delegations.get(delegation_id)
        if grant is None or grant.mission_id != mission_id:
            raise AuthorizationError("DELEGATION_INVALID")
        decision = self.authorization.decide(
            AuthorizationRequest(principal=actor, mission_id=mission_id, operation="REVOKE_DELEGATION",
                                 roe_level=mission.roe.level, mission_status=mission.status)
        )
        if decision.decision == Decision.DENY:
            self.kernel.record_delegation_event(
                mission_id=mission_id, actor=actor, event_type="DELEGATION_REVOCATION_DENIED",
                result="DENY", grant_id=delegation_id, data={"reason": decision.reason},
            )
            raise AuthorizationError(decision.reason)
        self.delegations[delegation_id] = DelegationGrant(
            **{**grant.__dict__, "revoked": True, "revoked_at": decision.evaluated_at,
               "revoked_by": actor, "revocation_reason": reason}
        )
        self.kernel.record_delegation_event(
            mission_id=mission_id, actor=actor, event_type="DELEGATION_REVOKED", result="SUCCESS",
            grant_id=delegation_id, data={"reason": reason, "decision_id": decision.decision_id,
                                           "policy_version": decision.policy_version},
        )

    def _workload_decision(
        self, *, principal: Principal, mission_id: str, operation: str, roe_level: RoeLevel,
        mission_status: MissionStatus, delegation_id: str | None, **kwargs: Any,
    ) -> Any:
        grant = self.delegations.get(delegation_id) if delegation_id else None
        decision = self.authorization.decide(
            AuthorizationRequest(principal=principal, mission_id=mission_id, operation=operation,
                                 roe_level=roe_level, mission_status=mission_status,
                                 delegation=grant, delegation_id=delegation_id, **kwargs)
        )
        self.kernel.record_delegation_event(
            mission_id=mission_id, actor=principal, event_type="DELEGATION_EVALUATED",
            result=decision.decision.value, grant_id=delegation_id or "none",
            data={"operation": operation, "reason": decision.reason,
                  "decision_id": decision.decision_id, "policy_version": decision.policy_version},
        )
        return decision

    def create_mission(self, *, actor: Principal, body: dict[str, Any]) -> ApiResponse:
        try:
            self._require_fields(body, "organization_id", "workspace_id", "title", "objective")
            self._validate_uuid(body["organization_id"])
            self._validate_uuid(body["workspace_id"])
            roe_level = RoeLevel(body.get("initial_roe_level", "OBSERVE"))
            denied = self._authorize(
                AuthorizationRequest(
                    principal=actor,
                    mission_id="CREATE",
                    operation="CREATE_MISSION",
                    roe_level=roe_level,
                    mission_status=MissionStatus.DRAFT,
                )
            )
            if denied:
                return denied
            mission = self.kernel.create_mission(
                actor=actor,
                organization_id=body["organization_id"],
                workspace_id=body["workspace_id"],
                title=body["title"],
                objective=body["objective"],
                roe_level=roe_level,
            )
        except (AuthorizationError, ValueError, TypeError, KeyError) as exc:
            return self._error(403 if str(exc) == "MISSION_CREATE_FORBIDDEN" else 422, str(exc))
        response = self._mission_payload(mission)
        return ApiResponse(
            status_code=201,
            body=response,
            headers={"Location": f"/missions/{mission.id}"},
        )

    def get_mission(self, *, actor: Principal, mission_id: str) -> ApiResponse:
        try:
            mission = self.kernel.get_mission(mission_id)
        except KeyError:
            return self._error(404, "NOT_FOUND")
        denied = self._authorize(
            AuthorizationRequest(
                principal=actor,
                mission_id=mission_id,
                operation="READ_MISSION",
                roe_level=mission.roe.level,
                mission_status=mission.status,
            )
        )
        if denied:
            return denied
        return ApiResponse(200, self._mission_payload(mission), {})

    def list_missions(self, *, actor: Principal) -> ApiResponse:
        """Return compact read-authorized Mission projections for Praetorium.

        This deliberately reuses Aquila's existing read policy rather than
        treating a UI route or Mission participation as an authority source.
        The detailed projection remains available only through ``get_mission``.
        """
        missions = [self.kernel.get_mission(mission_id) for mission_id in self.kernel.missions]
        if not missions:
            # A reader role remains required even when there is no Mission to
            # use as a policy context.
            denied = self._authorize(
                AuthorizationRequest(
                    principal=actor,
                    mission_id="LIST",
                    operation="READ_MISSION",
                    roe_level=RoeLevel.OBSERVE,
                    mission_status=MissionStatus.DRAFT,
                )
            )
            if denied:
                return denied
        summaries = []
        for mission in missions:
            denied = self._authorize(
                AuthorizationRequest(
                    principal=actor,
                    mission_id=mission.id,
                    operation="READ_MISSION",
                    roe_level=mission.roe.level,
                    mission_status=mission.status,
                )
            )
            if denied is None:
                summaries.append(self._mission_summary_payload(mission))
        return ApiResponse(200, {"missions": summaries}, {})

    def submit_command(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
        correlation_id: str | None = None,
    ) -> ApiResponse:
        try:
            self._validate_command_submission(body)
            mission = self.kernel.get_mission(mission_id)
            command_type = body["command_type"]
            requested_roe = mission.roe.level
            if command_type == "SET_ROE":
                requested_roe = RoeLevel(body["payload"].get("level", mission.roe.level.value))
            operation = "EXECUTE_ACTION" if command_type == "REQUEST_ACTION" else (
                "SET_ROE" if command_type == "SET_ROE" else "SUBMIT_COMMAND"
            )
            decision = self.authorization.decide(
                AuthorizationRequest(
                    principal=actor,
                    mission_id=mission_id,
                    operation=operation,
                    roe_level=requested_roe,
                    mission_status=mission.status,
                    side_effect_class=(
                        str(body["payload"].get("side_effect_class", "READ"))
                        if command_type == "REQUEST_ACTION"
                        else "READ"
                    ),
                    capability=(
                        str(body["payload"].get("capability"))
                        if command_type == "REQUEST_ACTION"
                        and body["payload"].get("capability") is not None
                        else None
                    ),
                    approval_present=bool(body["payload"].get("approval_present", False)),
                )
            )
            self.kernel.record_command_authorization(
                mission_id=mission_id,
                actor=actor,
                command_type=command_type,
                decision_id=decision.decision_id,
                decision=decision.decision.value,
                reason=decision.reason,
                policy_version=decision.policy_version,
                evaluated_at=decision.evaluated_at,
                correlation_id=correlation_id,
            )
            if decision.decision == Decision.DENY and not (
                command_type == "REQUEST_ACTION" and decision.reason == "APPROVAL_REQUIRED"
            ):
                status = 409 if decision.reason == "MISSION_TERMINAL" else 403
                return self._error(status, decision.reason)
            result = self.kernel.submit_command(
                mission_id=mission_id,
                actor=actor,
                expected_version=body["expected_version"],
                idempotency_key=body["idempotency_key"],
                command_type=command_type,
                payload=body["payload"],
                requested_by=actor,
                correlation_id=correlation_id,
            )
            if result.status == "ACCEPTED" and command_type in {"PAUSE", "SUSPEND", "RESUME", "CANCEL"}:
                self._signal_mission_executions(
                    mission_id,
                    "CANCEL" if command_type == "CANCEL" else (
                        "PAUSE" if command_type == "SUSPEND" else command_type
                    ),
                    str(body["payload"].get("reason", command_type.lower())),
                )
        except KeyError:
            return self._error(404, "NOT_FOUND")
        except (ValueError, TypeError) as exc:
            return self._error(422, str(exc))

        if result.error_code == "VERSION_CONFLICT":
            return self._error(409, result.error_code, current_version=result.mission_version)
        if result.error_code in {"FORBIDDEN", "ROE_DENIED"}:
            return self._error(403, result.error_code, current_version=result.mission_version)
        if result.error_code == "MISSION_TERMINAL":
            return self._error(409, result.error_code, current_version=result.mission_version)
        if result.status == "REJECTED":
            return self._error(422, result.error_code or "INVALID_REQUEST", current_version=result.mission_version)
        status_code = 202 if result.status == "AWAITING_APPROVAL" else 200
        return ApiResponse(status_code, self._command_payload(result), {})

    def execute_action(
        self,
        *,
        mission_id: str,
        action_id: str,
        worker: Principal,
        delegation_id: str | None = None,
        fail_after_side_effect: bool = False,
    ) -> str:
        """Run an accepted action through the durable execution boundary."""
        mission = self.kernel.get_mission(mission_id)
        action = mission.actions[action_id]
        approval_present = bool(self.kernel.side_effects.get(action_id)) or any(
            approval.action.id == action_id and approval.status == "APPROVED"
            for approval in self.kernel.approvals.values()
        )
        decision = self._workload_decision(
            principal=worker, mission_id=mission_id, operation="EXECUTE_ACTION",
            roe_level=mission.roe.level, mission_status=mission.status, delegation_id=delegation_id,
            side_effect_class=action.side_effect_class, capability=action.capability,
            approval_present=approval_present,
        )
        self.kernel.record_execution_authorization(
            mission_id=mission_id,
            action_id=action_id,
            worker=worker,
            decision_id=decision.decision_id,
            decision=decision.decision.value,
            reason=decision.reason,
            policy_version=decision.policy_version,
            evaluated_at=decision.evaluated_at,
            delegation_id=delegation_id,
        )
        if decision.decision == Decision.DENY:
            self.kernel.reject_action_execution(
                mission_id=mission_id,
                action_id=action_id,
                worker=worker,
                error_code=decision.reason,
            )
            raise AuthorizationError(decision.reason)
        self.kernel.validate_action_execution(
            mission_id=mission_id,
            action_id=action_id,
            worker=worker,
        )
        execution_id = self.action_executions.get(action_id)
        if execution_id is None:
            record = self.execution.start(
                mission_id=mission_id,
                command_id=action.command_id,
                idempotency_key=f"action:{action_id}",
                input={
                    "action_id": action.id,
                    "capability": action.capability,
                    "arguments": action.arguments,
                    "target": action.target,
                    "side_effect_class": action.side_effect_class,
                },
            )
            execution_id = record.execution_id
            self.action_executions[action_id] = execution_id
        else:
            record = self.execution.query(execution_id)

        if record.state == ExecutionState.CANCELLED:
            raise AuthorizationError("EXECUTION_CANCELLED")
        if record.state == ExecutionState.FAILED:
            self.execution.recover(execution_id)

        try:
            outcome = self.kernel.execute_action(
                mission_id=mission_id,
                action_id=action_id,
                worker=worker,
                fail_after_side_effect=fail_after_side_effect,
            )
        except WorkerKilled:
            self.execution.fail(execution_id, "worker killed after external side effect")
            raise
        self.execution.complete(execution_id, {"outcome": outcome})
        return outcome

    def run_scout(
        self,
        *,
        mission_id: str,
        scout: Principal,
        delegation_id: str | None = None,
        runtime: CognitionRuntimeAdapter,
        query: str,
        granted_capabilities: frozenset[str],
        evidence: tuple[ScoutEvidence, ...] = (),
    ) -> ScoutResult:
        """Run a bounded Scout without exposing Mission mutation authority.

        The Scout is authorized as a workload read of the current Mission and
        receives only a stable context projection.  Read observations are not
        authoritative Mission events.  A model-backed runtime emits only its
        digest-only invocation provenance as an append-only audit fact; this
        never changes Mission state or gives the model authority.
        """
        mission = self.kernel.get_mission(mission_id)
        decision = self._workload_decision(
            principal=scout, mission_id=mission_id, operation="READ_MISSION",
            roe_level=mission.roe.level, mission_status=mission.status, delegation_id=delegation_id,
        )
        if decision.decision == Decision.DENY:
            raise AuthorizationError(decision.reason)
        try:
            result = runtime.run_scout(
                ScoutRequest(
                    context=MissionContext.from_mission(mission),
                    scout=scout,
                    query=query,
                    granted_capabilities=granted_capabilities,
                    evidence=evidence,
                )
            )
        except ModelInvocationError as exc:
            self._record_model_invocation(
                mission_id=mission_id,
                scout=scout,
                provenance=exc.provenance,
                result="FAILED",
            )
            raise
        if result.model_invocation:
            self._record_model_invocation(
                mission_id=mission_id,
                scout=scout,
                provenance=result.model_invocation,
                result="SUCCESS",
            )
        return result

    def _record_model_invocation(
        self,
        *,
        mission_id: str,
        scout: Principal,
        provenance: ModelInvocationProvenance,
        result: str,
    ) -> None:
        self.kernel.record_model_invocation(
            mission_id=mission_id,
            actor=scout,
            invocation_id=provenance.invocation_id,
            correlation_id=provenance.invocation_id,
            result=result,
            data={
                "provider": provenance.provider,
                "model": provenance.model,
                "response_id": provenance.response_id,
                "attempts": provenance.attempts,
                "timeout_seconds": provenance.timeout_seconds,
                "request_digest": provenance.request_digest,
                "response_digest": provenance.response_digest,
                "error_code": provenance.error_code,
            },
        )

    def retrieve_knowledge(
        self,
        *,
        mission_id: str,
        worker: Principal,
        delegation_id: str | None = None,
        tabula: TabulaRetrievalAdapter,
        query: str,
        limit: int = 10,
    ) -> tuple[RetrievedKnowledge, ...]:
        """Retrieve scoped Tabula context under a fresh workload authorization."""
        mission = self.kernel.get_mission(mission_id)
        decision = self._workload_decision(
            principal=worker, mission_id=mission_id, operation="READ_KNOWLEDGE",
            roe_level=mission.roe.level, mission_status=mission.status, delegation_id=delegation_id,
        )
        if decision.decision == Decision.DENY:
            raise AuthorizationError(decision.reason)
        return tabula.retrieve(scope=KnowledgeScope.from_mission(mission), query=query, limit=limit)

    def retrieve_federated_corpus(
        self,
        *,
        mission_id: str,
        worker: Principal,
        delegation_id: str | None = None,
        client: TabulaCorpusClient,
        token: Callable[[], str],
        binding: ScopeBinding,
        query: str,
        correlation_id: str | None = None,
        intent: str = "SCOUT_EVIDENCE",
        limit: int = 10,
    ) -> CorpusRead:
        """Authorize, invoke, and audit one narrow Tabula corpus read.

        The delegated bearer is held only by the injected token supplier.  Mission
        audit receives Tabula's correlation reference and registry references, never
        the token, query or bearer tokens.
        """
        mission = self.kernel.get_mission(mission_id)
        correlation_id = correlation_id or str(uuid4())
        self._validate_uuid(correlation_id)
        invocation_id = str(uuid4())
        decision = self._workload_decision(
            principal=worker, mission_id=mission_id, operation="READ_KNOWLEDGE",
            roe_level=mission.roe.level, mission_status=mission.status, delegation_id=delegation_id,
        )
        self.kernel.record_external_read_authorization(
            mission_id=mission_id, actor=worker, target_product="TABULA",
            operation="TABULA_CORPUS_READ", invocation_id=invocation_id,
            decision_id=decision.decision_id, decision=decision.decision.value,
            reason=decision.reason, policy_version=decision.policy_version,
            evaluated_at=decision.evaluated_at, correlation_id=correlation_id,
            delegation_id=delegation_id,
        )
        if decision.decision == Decision.DENY:
            self.kernel.record_external_read_result(
                mission_id=mission_id, actor=worker, target_product="TABULA",
                operation="TABULA_CORPUS_READ", invocation_id=invocation_id,
                correlation_id=correlation_id, result="DENY", data={"error_code": decision.reason},
            )
            raise AuthorizationError(decision.reason)
        try:
            result = client.read(
                token=token, binding=binding, query=query, correlation_id=correlation_id,
                intent=intent, limit=limit,
            )
        except (CorpusReadError, ValueError) as exc:
            data = exc.audit_data() if isinstance(exc, CorpusReadError) else {"error_code": "INVALID_REQUEST"}
            self.kernel.record_external_read_result(
                mission_id=mission_id, actor=worker, target_product="TABULA",
                operation="TABULA_CORPUS_READ", invocation_id=invocation_id,
                correlation_id=correlation_id, result="REJECTED", data=data,
            )
            raise
        self.kernel.record_external_read_result(
            mission_id=mission_id, actor=worker, target_product="TABULA",
            operation="TABULA_CORPUS_READ", invocation_id=invocation_id,
            correlation_id=correlation_id, result="SUCCESS", data=result.audit_data(),
        )
        return result

    def retrieve_federated_registry(
        self,
        *,
        mission_id: str,
        worker: Principal,
        delegation_id: str | None = None,
        client: TabulaRegistryClient,
        token: Callable[[], str],
        binding: ScopeBinding,
        query: str,
        correlation_id: str | None = None,
        intent: str = "SCOUT_DISCOVERY",
        limit: int = 10,
    ) -> RegistryDiscovery:
        """Authorize, invoke, and audit one narrow Tabula Registry discovery.

        The delegated bearer is held only by the injected token supplier.  Mission
        audit receives Tabula's correlation reference and registry references, never
        the token, query or bearer tokens.
        """
        mission = self.kernel.get_mission(mission_id)
        correlation_id = correlation_id or str(uuid4())
        self._validate_uuid(correlation_id)
        invocation_id = str(uuid4())
        decision = self._workload_decision(
            principal=worker, mission_id=mission_id, operation="READ_KNOWLEDGE",
            roe_level=mission.roe.level, mission_status=mission.status, delegation_id=delegation_id,
        )
        self.kernel.record_external_read_authorization(
            mission_id=mission_id, actor=worker, target_product="TABULA",
            operation="TABULA_REGISTRY_READ", invocation_id=invocation_id,
            decision_id=decision.decision_id, decision=decision.decision.value,
            reason=decision.reason, policy_version=decision.policy_version,
            evaluated_at=decision.evaluated_at, correlation_id=correlation_id,
            delegation_id=delegation_id,
        )
        if decision.decision == Decision.DENY:
            self.kernel.record_external_read_result(
                mission_id=mission_id, actor=worker, target_product="TABULA",
                operation="TABULA_REGISTRY_READ", invocation_id=invocation_id,
                correlation_id=correlation_id, result="DENY", data={"error_code": decision.reason},
            )
            raise AuthorizationError(decision.reason)
        try:
            result = client.discover(
                token=token, binding=binding, query=query, correlation_id=correlation_id,
                intent=intent, limit=limit,
            )
        except (RegistryReadError, ValueError) as exc:
            data = exc.audit_data() if isinstance(exc, RegistryReadError) else {"error_code": "INVALID_REQUEST"}
            self.kernel.record_external_read_result(
                mission_id=mission_id, actor=worker, target_product="TABULA",
                operation="TABULA_REGISTRY_READ", invocation_id=invocation_id,
                correlation_id=correlation_id, result="REJECTED", data=data,
            )
            raise
        self.kernel.record_external_read_result(
            mission_id=mission_id, actor=worker, target_product="TABULA",
            operation="TABULA_REGISTRY_READ", invocation_id=invocation_id,
            correlation_id=correlation_id, result="SUCCESS", data=result.audit_data(),
        )
        return result

    def run_tabula_scout(
        self,
        *,
        mission_id: str,
        scout: Principal,
        delegation_id: str | None = None,
        runtime: CognitionRuntimeAdapter,
        tabula: TabulaRetrievalAdapter,
        query: str,
        granted_capabilities: frozenset[str],
        limit: int = 10,
    ) -> ScoutResult:
        """Retrieve scoped evidence from Tabula, then run the read-only Scout."""
        evidence = tuple(
            ScoutEvidence(
                source=item.source,
                summary=item.summary,
                observed_at=item.observed_at,
            )
            for item in self.retrieve_knowledge(
                mission_id=mission_id,
                worker=scout,
                delegation_id=delegation_id,
                tabula=tabula,
                query=query,
                limit=limit,
            )
        )
        return self.run_scout(
            mission_id=mission_id,
            scout=scout,
            delegation_id=delegation_id,
            runtime=runtime,
            query=query,
            granted_capabilities=granted_capabilities,
            evidence=evidence,
        )

    def invoke_read_tool(
        self,
        *,
        mission_id: str,
        worker: Principal,
        delegation_id: str | None = None,
        fabrica: ToolExecutionAdapter,
        capability: str,
        arguments: dict[str, Any],
        correlation_id: str | None = None,
    ) -> ToolResult:
        """Authorize, broker, and audit one declared read-only Fabrica tool."""
        mission = self.kernel.get_mission(mission_id)
        invocation_id = str(uuid4())
        correlation_id = correlation_id or str(uuid4())
        definition = fabrica.resolve(capability)
        decision = self._workload_decision(
            principal=worker, mission_id=mission_id, operation="READ_TOOL",
            roe_level=mission.roe.level, mission_status=mission.status, delegation_id=delegation_id,
            capability=capability,
        )
        reason = decision.reason
        allowed = decision.decision == Decision.ALLOW
        if definition.side_effect_class != "READ":
            allowed, reason = False, "TOOL_ACTION_REQUIRED"
        elif capability in mission.roe.denied_capabilities or (
            mission.roe.allowed_capabilities and capability not in mission.roe.allowed_capabilities
        ):
            allowed, reason = False, "ROE_CAPABILITY_DENIED"
        self.kernel.record_tool_authorization(
            mission_id=mission_id,
            actor=worker,
            capability=capability,
            invocation_id=invocation_id,
            decision_id=decision.decision_id,
            decision=Decision.ALLOW.value if allowed else Decision.DENY.value,
            reason=reason,
            policy_version=decision.policy_version,
            evaluated_at=decision.evaluated_at,
            correlation_id=correlation_id,
            delegation_id=delegation_id,
        )
        if not allowed:
            self.kernel.record_tool_result(
                mission_id=mission_id,
                actor=worker,
                capability=capability,
                invocation_id=invocation_id,
                correlation_id=correlation_id,
                result="REJECTED",
                data={"error_code": reason},
            )
            raise AuthorizationError(reason)
        try:
            result = fabrica.invoke(
                ToolInvocation(
                    invocation_id=invocation_id,
                    mission_id=mission_id,
                    capability=capability,
                    arguments=arguments,
                    authorization_id=decision.decision_id,
                    correlation_id=correlation_id,
                )
            )
        except FabricaError as exc:
            self.kernel.record_tool_result(
                mission_id=mission_id,
                actor=worker,
                capability=capability,
                invocation_id=invocation_id,
                correlation_id=correlation_id,
                result="REJECTED",
                data={"error_code": str(exc)},
            )
            raise
        self.kernel.record_tool_result(
            mission_id=mission_id,
            actor=worker,
            capability=capability,
            invocation_id=invocation_id,
            correlation_id=correlation_id,
            result="SUCCESS",
            data={"output": result.output},
        )
        return result

    def decide_approval(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
    ) -> ApiResponse:
        try:
            self._require_fields(body, "approval_id", "expected_mission_version", "decision", "reason")
            approval = self.kernel.approvals[str(body["approval_id"])]
            if approval.mission_id != mission_id:
                return self._error(404, "NOT_FOUND")
            mission = self.kernel.get_mission(mission_id)
            decision = self.authorization.decide(
                AuthorizationRequest(
                    principal=actor,
                    mission_id=mission_id,
                    operation="DECIDE_APPROVAL",
                    roe_level=mission.roe.level,
                    mission_status=mission.status,
                )
            )
            self.kernel.record_approval_authorization(
                mission_id=mission_id,
                approval_id=approval.id,
                actor=actor,
                decision_id=decision.decision_id,
                decision=decision.decision.value,
                reason=decision.reason,
                policy_version=decision.policy_version,
                evaluated_at=decision.evaluated_at,
            )
            if decision.decision == Decision.DENY:
                status = 409 if decision.reason == "MISSION_TERMINAL" else 403
                return self._error(status, decision.reason)
            approval = self.kernel.decide_approval(
                approval_id=str(body["approval_id"]),
                approver=actor,
                expected_mission_version=int(body["expected_mission_version"]),
                decision=str(body["decision"]),
                reason=str(body["reason"]),
            )
        except KeyError:
            return self._error(404, "NOT_FOUND")
        except AuthorizationError as exc:
            if str(exc) == "FORBIDDEN":
                return self._error(403, "FORBIDDEN")
            if str(exc) == "APPROVAL_STALE":
                return self._error(409, "APPROVAL_STALE")
            return self._error(409, str(exc))
        except (ValueError, TypeError) as exc:
            return self._error(422, str(exc))
        if approval.mission_id != mission_id:
            return self._error(404, "NOT_FOUND")
        return ApiResponse(200, self._approval_payload(approval), {})

    def list_approvals(self, *, actor: Principal, mission_id: str) -> ApiResponse:
        """Return approvals only after Aquila authorizes Mission read access."""
        try:
            mission = self.kernel.get_mission(mission_id)
        except KeyError:
            return self._error(404, "NOT_FOUND")
        denied = self._authorize(
            AuthorizationRequest(
                principal=actor, mission_id=mission_id, operation="READ_MISSION",
                roe_level=mission.roe.level, mission_status=mission.status,
            )
        )
        if denied:
            return denied
        approvals = [
            self._approval_payload(approval)
            for approval in self.kernel.approvals.values()
            if approval.mission_id == mission_id
        ]
        return ApiResponse(200, {"mission_id": mission_id, "approvals": approvals}, {})

    def get_timeline(
        self,
        *,
        actor: Principal,
        mission_id: str,
        limit: int = 50,
        after_sequence: int = 0,
    ) -> ApiResponse:
        if limit < 1 or limit > 200 or after_sequence < 0:
            return self._error(422, "INVALID_REQUEST")
        try:
            mission = self.kernel.get_mission(mission_id)
            events = self.kernel.timeline(mission_id)
        except KeyError:
            return self._error(404, "NOT_FOUND")
        denied = self._authorize(
            AuthorizationRequest(
                principal=actor,
                mission_id=mission_id,
                operation="READ_TIMELINE",
                roe_level=mission.roe.level,
                mission_status=mission.status,
            )
        )
        if denied:
            return denied
        selected = [event for event in events if event.sequence > after_sequence]
        page = selected[:limit]
        has_more = len(selected) > len(page)
        next_cursor = str(page[-1].sequence) if has_more and page else None
        return ApiResponse(
            200,
            {
                "mission_id": mission_id,
                "events": [_audit_payload(event) for event in page],
                "next_cursor": next_cursor,
                "has_more": has_more,
            },
            {},
        )

    def cancel_mission(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
        correlation_id: str | None = None,
    ) -> ApiResponse:
        try:
            self._require_fields(body, "expected_version", "idempotency_key", "reason")
            response = self.submit_command(
                actor=actor,
                mission_id=mission_id,
                body={
                    "expected_version": int(body["expected_version"]),
                    "idempotency_key": str(body["idempotency_key"]),
                    "command_type": "CANCEL",
                    "payload": {},
                },
                correlation_id=correlation_id,
            )
        except KeyError:
            return self._error(404, "NOT_FOUND")
        except (ValueError, TypeError) as exc:
            return self._error(422, str(exc))
        if response.status_code not in {200, 202}:
            return response
        return self.get_mission(actor=actor, mission_id=mission_id)

    def _signal_mission_executions(self, mission_id: str, command: str, reason: str) -> None:
        for execution_id in tuple(self.action_executions.values()):
            record = self.execution.query(execution_id)
            if record.mission_id != mission_id:
                continue
            try:
                if command == "CANCEL":
                    self.execution.cancel(execution_id, reason)
                else:
                    self.execution.signal(execution_id, command)
            except ValueError:
                continue

    @staticmethod
    def _require_fields(body: dict[str, Any], *names: str) -> None:
        if not isinstance(body, dict):
            raise TypeError("body must be an object")
        missing = [name for name in names if name not in body]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

    @staticmethod
    def _validate_command_submission(body: Any) -> None:
        if not isinstance(body, dict):
            raise ValueError("INVALID_COMMAND_SUBMISSION")
        required = {"expected_version", "idempotency_key", "command_type", "payload"}
        if set(body) != required:
            raise ValueError("INVALID_COMMAND_SUBMISSION")
        version = body["expected_version"]
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise ValueError("INVALID_COMMAND_SUBMISSION")
        key = body["idempotency_key"]
        if not isinstance(key, str) or not 1 <= len(key) <= 256:
            raise ValueError("INVALID_COMMAND_SUBMISSION")
        command_type = body["command_type"]
        if not isinstance(command_type, str):
            raise ValueError("INVALID_COMMAND_SUBMISSION")
        if not isinstance(body["payload"], dict):
            raise ValueError("INVALID_COMMAND_SUBMISSION")

    @staticmethod
    def _validate_uuid(value: str) -> None:
        UUID(str(value))

    def _authorize(
        self,
        request: AuthorizationRequest,
        *,
        soft_reasons: set[str] | None = None,
    ) -> ApiResponse | None:
        decision = self.authorization.decide(request)
        if decision.decision == Decision.ALLOW or decision.reason in (soft_reasons or set()):
            return None
        status = 409 if decision.reason == "MISSION_TERMINAL" else 403
        return self._error(status, decision.reason)

    @staticmethod
    def _principal_from_body(value: Any, fallback: Principal) -> Principal:
        if value is None:
            return fallback
        if not isinstance(value, dict) or "type" not in value or "subject" not in value:
            raise ValueError("requested_by must contain type and subject")
        return Principal(
            type=PrincipalType(value["type"]),
            subject=str(value["subject"]),
            roles=frozenset(),
        )

    @staticmethod
    def _command_payload(result: Any) -> dict[str, Any]:
        return {
            "command_id": result.command_id,
            "mission_id": result.mission_id,
            "status": result.status,
            "mission_version": result.mission_version,
            "approval_id": result.approval_id,
            "error_code": result.error_code,
            "message": result.message,
        }

    @staticmethod
    def _mission_payload(mission: Any) -> dict[str, Any]:
        roe = mission.roe
        last_event_id = None
        return {
            "id": mission.id,
            "schema_version": "1.0",
            "organization_id": mission.organization_id,
            "workspace_id": mission.workspace_id,
            "project_id": None,
            "environment_id": None,
            "title": mission.title,
            "objective": mission.objective,
            "status": mission.status.value,
            "version": mission.version,
            "roe": {
                "schema_version": "1.0",
                "revision": roe.revision,
                "level": roe.level.value,
                "effective_at": roe.effective_at,
                "changed_by": _principal_payload(roe.changed_by),
                "allowed_capabilities": sorted(roe.allowed_capabilities),
                "denied_capabilities": sorted(roe.denied_capabilities),
                "approval": {
                    "required_for": sorted(roe.approval_required_for),
                    "minimum_approvals": 1 if roe.approval_required_for else 0,
                },
                "reason": roe.reason,
            },
            "constraints": [
                {
                    "id": constraint.id,
                    "text": constraint.text,
                    "severity": constraint.severity,
                    "added_at": constraint.added_at,
                    "added_by": _principal_payload(constraint.added_by),
                }
                for constraint in mission.constraints
            ],
            "participants": [
                {
                    "principal": _principal_payload(participant.principal),
                    "role": participant.role,
                    "scope": participant.scope,
                }
                for participant in mission.participants
            ],
            "labels": {},
            "active_execution": None,
            "last_event_id": last_event_id,
            "created_at": mission.created_at,
            "updated_at": mission.updated_at,
            "created_by": _principal_payload(mission.created_by),
        }

    @staticmethod
    def _mission_summary_payload(mission: Any) -> dict[str, Any]:
        return {
            "id": mission.id,
            "title": mission.title,
            "status": mission.status.value,
            "version": mission.version,
            "organization_id": mission.organization_id,
            "workspace_id": mission.workspace_id,
            "updated_at": mission.updated_at,
        }

    @staticmethod
    def _approval_payload(approval: Any) -> dict[str, Any]:
        return {
            "id": approval.id,
            "schema_version": "1.0",
            "mission_id": approval.mission_id,
            "command_id": approval.command_id,
            "action_id": approval.action.id,
            "mission_version": approval.mission_version,
            "roe_revision": approval.roe_revision,
            "action_hash": approval.action_hash,
            "scope": {
                "capability": approval.action.capability,
                "side_effect_class": approval.action.side_effect_class,
                "target": approval.action.target,
                "environment_id": None,
            },
            "requested_by": _principal_payload(approval.requested_by),
            "approver": _principal_payload(approval.approver) if approval.approver else None,
            "status": approval.status,
            "decision_reason": approval.decision_reason,
            "requested_at": approval.action.requested_at,
            "decided_at": approval.decided_at,
            "expires_at": approval.expires_at,
            "consumed_at": approval.consumed_at,
        }

    @staticmethod
    def _error(status_code: int, code: str, *, current_version: int | None = None) -> ApiResponse:
        body = {
            "code": code,
            "message": code,
            "correlation_id": "service-generated",
            "current_version": current_version,
        }
        return ApiResponse(status_code, body, {})


def _principal_payload(principal: Principal | None) -> dict[str, Any] | None:
    if principal is None:
        return None
    return {"type": principal.type.value, "subject": principal.subject}


def _audit_payload(event: Any) -> dict[str, Any]:
    return {
        "id": event.id,
        "schema_version": "1.0",
        "sequence": event.sequence,
        "mission_id": event.mission_id,
        "mission_version": event.mission_version,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at,
        "recorded_at": event.occurred_at,
        "actor": _principal_payload(event.actor),
        "requested_by": None,
        "delegated_by": None,
        "executed_by": None,
        "resource": {"type": "Mission", "id": event.mission_id},
        "result": event.result,
        "command_id": event.command_id,
        "approval_id": event.approval_id,
        "correlation_id": event.correlation_id,
        "causation_id": event.causation_id,
        "data": event.data,
    }


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, frozenset | set):
        return sorted(_encode(item) for item in value)
    if isinstance(value, list | tuple):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if is_dataclass(value):
        return {field.name: _encode(getattr(value, field.name)) for field in fields(value)}
    return value


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("DELEGATION_EXPIRY_REQUIRED")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("DELEGATION_EXPIRY_REQUIRED") from exc
    if parsed.tzinfo is None:
        raise ValueError("DELEGATION_EXPIRY_REQUIRED")
    return parsed.astimezone(timezone.utc)
