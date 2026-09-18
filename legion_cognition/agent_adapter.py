"""Compatibility bridge from persistent-Agent cognition to legacy Scout runtime."""

from __future__ import annotations

from uuid import UUID

from legion_kernel import Principal, PrincipalType
from legion_runtime import AgentRole
from legion_runtime.cognition import (
    AgentCognitionRequest,
    AgentCognitionResult,
    CognitionRejected,
    ReadOnlyCognition,
)

from .scout import (
    CognitionRuntimeAdapter,
    MissionContext,
    SCOUT_MISSION_READ_CAPABILITY,
    ScoutRequest,
)


class LegacyScoutRuntimeBridge(ReadOnlyCognition):
    """Keep the historical workload-shaped request behind the canonical port."""

    def __init__(self, runtime: CognitionRuntimeAdapter) -> None:
        self.runtime = runtime

    def run(self, request: AgentCognitionRequest) -> AgentCognitionResult:
        self._validate(request)
        legacy = ScoutRequest(
            context=MissionContext(
                mission_id=request.context.mission_id,
                mission_version=request.context.mission_version,
                title=request.context.title,
                objective=request.context.objective,
                status=request.context.status,
                roe_level=request.context.roe_level,
                constraints=request.context.constraints,
            ),
            scout=Principal(PrincipalType.WORKLOAD, request.workload_subject),
            query=request.objective,
            granted_capabilities=frozenset({SCOUT_MISSION_READ_CAPABILITY}),
        )
        result = self.runtime.run_scout(legacy)
        if (
            result.mission_id != request.mission_id
            or result.mission_version != request.mission_version
            or result.scout.subject != request.workload_subject
        ):
            raise CognitionRejected("COGNITION_IDENTITY_MISMATCH")
        return AgentCognitionResult(
            request_id=request.request_id,
            agent_id=request.agent_id,
            work_item_id=request.work_item_id,
            attempt_id=request.attempt_id,
            mission_id=request.mission_id,
            mission_version=request.mission_version,
            summary=result.recommendation,
            evidence_references=tuple(item.source for item in result.evidence),
        )

    @staticmethod
    def _validate(request: AgentCognitionRequest) -> None:
        if request.agent_role != AgentRole.SCOUT:
            raise CognitionRejected("SCOUT_AGENT_REQUIRED")
        for value in (
            request.request_id,
            request.agent_id,
            request.work_item_id,
            request.attempt_id,
            request.mission_id,
        ):
            try:
                UUID(value)
            except (TypeError, ValueError, AttributeError) as exc:
                raise CognitionRejected("COGNITION_IDENTITY_INVALID") from exc
        if request.logical_capability != "read_only_analysis":
            raise CognitionRejected("COGNITION_CAPABILITY_DENIED")
        if not request.workload_subject.strip() or not request.objective.strip():
            raise CognitionRejected("COGNITION_REQUEST_INVALID")
        if (
            request.context.mission_id != request.mission_id
            or request.context.mission_version != request.mission_version
        ):
            raise CognitionRejected("COGNITION_CONTEXT_MISMATCH")
        if request.required_capabilities != ("read_only_analysis",):
            raise CognitionRejected("COGNITION_CAPABILITY_DENIED")
