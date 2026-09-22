"""Safe read-only projection of a Mission's persistent organization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .repository import AgentRepository


@dataclass(frozen=True)
class MissionAgentView:
    agent_id: str
    display_name: str
    role: str
    assignment_status: str


@dataclass(frozen=True)
class MissionEvidenceView:
    evidence_reference_id: str
    external_record_id: str
    external_revision: str
    canonical_uri: str
    retrieved_at: str


@dataclass(frozen=True)
class MissionWorkView:
    work_item_id: str
    work_kind: str
    objective: str
    status: str
    created_at: str
    updated_at: str
    result_summary: str | None
    result_digest: str | None
    evidence: tuple[MissionEvidenceView, ...]
    cognition_turns: tuple[dict, ...] = ()


@dataclass(frozen=True)
class MissionOrganizationSnapshot:
    mission_id: str
    agents: tuple[MissionAgentView, ...]
    work: tuple[MissionWorkView, ...]


class MissionOrganizationReadModel(Protocol):
    def snapshot(
        self, *, organization_id: str, workspace_id: str, mission_id: str
    ) -> MissionOrganizationSnapshot: ...


class RepositoryMissionOrganizationReadModel:
    """Build a tenant-scoped projection through Runtime's repository contract."""

    def __init__(self, repository: AgentRepository) -> None:
        self.repository = repository

    def snapshot(
        self, *, organization_id: str, workspace_id: str, mission_id: str
    ) -> MissionOrganizationSnapshot:
        agent_views: list[MissionAgentView] = []
        for assignment in self.repository.list_assignments_for_mission(mission_id):
            agent = self.repository.get_agent(assignment.agent_id)
            if agent is None:
                continue
            if (
                agent.organization_id != organization_id
                or agent.workspace_id != workspace_id
            ):
                raise ValueError("RUNTIME_PROJECTION_SCOPE_MISMATCH")
            agent_views.append(
                MissionAgentView(
                    agent_id=agent.agent_id,
                    display_name=agent.display_name,
                    role=agent.role.value,
                    assignment_status=assignment.status.value,
                )
            )

        work_views: list[MissionWorkView] = []
        for work in self.repository.list_work_for_mission(mission_id):
            centurion = self.repository.get_agent(work.centurion_agent_id)
            scout = self.repository.get_agent(work.scout_agent_id)
            if centurion is None or scout is None:
                raise ValueError("RUNTIME_PROJECTION_AGENT_MISSING")
            for agent in (centurion, scout):
                if (
                    agent.organization_id != organization_id
                    or agent.workspace_id != workspace_id
                ):
                    raise ValueError("RUNTIME_PROJECTION_SCOPE_MISMATCH")
            result = self.repository.get_work_result(work.work_item_id)
            references = self.repository.list_work_evidence_references(
                work_item_id=work.work_item_id
            )
            if result is not None:
                accepted_ids = set(result.evidence_references)
                references = [
                    reference
                    for reference in references
                    if reference.evidence_reference_id in accepted_ids
                ]
            else:
                references = []
            work_views.append(
                MissionWorkView(
                    work_item_id=work.work_item_id,
                    work_kind=work.kind.value,
                    objective=work.objective,
                    status=work.status.value,
                    created_at=work.created_at,
                    updated_at=work.updated_at,
                    result_summary=result.summary if result else None,
                    result_digest=result.content_digest if result else None,
                    cognition_turns=tuple(self.repository.list_cognition_turns(work.work_item_id)),
                    evidence=tuple(
                        MissionEvidenceView(
                            evidence_reference_id=reference.evidence_reference_id,
                            external_record_id=reference.external_record_id,
                            external_revision=reference.external_revision,
                            canonical_uri=reference.canonical_uri,
                            retrieved_at=reference.retrieved_at,
                        )
                        for reference in references
                    ),
                )
            )
        return MissionOrganizationSnapshot(
            mission_id=mission_id,
            agents=tuple(agent_views),
            work=tuple(work_views),
        )
