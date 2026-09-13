"""A minimal, provider-neutral read-only Scout cognition adapter.

This module deliberately contains no model SDK, tool client, or Mission
mutation API.  It proves the contract through which a future cognition runtime
receives bounded Mission context and returns structured observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from legion_kernel import Principal, PrincipalType


class ReadOnlyScoutError(ValueError):
    """Raised when a Scout request exceeds its read-only contract."""


SCOUT_MISSION_READ_CAPABILITY = "read.mission"


@dataclass(frozen=True)
class MissionContext:
    """The minimum Mission projection supplied to a cognition runtime."""

    mission_id: str
    mission_version: int
    title: str
    objective: str
    status: str
    roe_level: str
    constraints: tuple[str, ...]

    @classmethod
    def from_mission(cls, mission: Any) -> "MissionContext":
        return cls(
            mission_id=mission.id,
            mission_version=mission.version,
            title=mission.title,
            objective=mission.objective,
            status=mission.status.value,
            roe_level=mission.roe.level.value,
            constraints=tuple(constraint.text for constraint in mission.constraints),
        )


@dataclass(frozen=True)
class ScoutEvidence:
    """A provenance-bearing observation returned by a Scout."""

    source: str
    summary: str
    observed_at: str


@dataclass(frozen=True)
class ScoutRequest:
    """An explicitly capability-bounded request for read-only observation."""

    context: MissionContext
    scout: Principal
    query: str
    granted_capabilities: frozenset[str]
    evidence: tuple[ScoutEvidence, ...] = ()


@dataclass(frozen=True)
class ScoutResult:
    """Structured output that can be displayed or attached as evidence."""

    mission_id: str
    mission_version: int
    scout: Principal
    query: str
    evidence: tuple[ScoutEvidence, ...]
    recommendation: str


class CognitionRuntimeAdapter(Protocol):
    """Replaceable runtime contract for the first read-only Legion agent."""

    def run_scout(self, request: ScoutRequest) -> ScoutResult: ...


def validate_scout_request(request: ScoutRequest) -> None:
    """Enforce the provider-independent, read-only Scout contract."""
    if request.scout.type != PrincipalType.WORKLOAD:
        raise ReadOnlyScoutError("SCOUT_WORKLOAD_REQUIRED")
    if not request.query.strip():
        raise ReadOnlyScoutError("SCOUT_QUERY_REQUIRED")
    if SCOUT_MISSION_READ_CAPABILITY not in request.granted_capabilities:
        raise ReadOnlyScoutError("SCOUT_MISSION_READ_REQUIRED")
    if any(not capability.startswith("read.") for capability in request.granted_capabilities):
        raise ReadOnlyScoutError("SCOUT_CAPABILITY_DENIED")
    for item in request.evidence:
        if not item.source or not item.summary or not item.observed_at:
            raise ReadOnlyScoutError("SCOUT_EVIDENCE_INVALID")


class InMemoryScoutRuntime:
    """Deterministic reference Scout with no model or tool dependency."""

    _REQUIRED_CAPABILITY = SCOUT_MISSION_READ_CAPABILITY

    def run_scout(self, request: ScoutRequest) -> ScoutResult:
        validate_scout_request(request)
        count = len(request.evidence)
        recommendation = (
            f"Scout collected {count} observation{'s' if count != 1 else ''} "
            f"for: {request.query}"
        )
        return ScoutResult(
            mission_id=request.context.mission_id,
            mission_version=request.context.mission_version,
            scout=request.scout,
            query=request.query,
            evidence=request.evidence,
            recommendation=recommendation,
        )
