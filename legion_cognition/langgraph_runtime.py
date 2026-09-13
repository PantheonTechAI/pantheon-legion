"""LangGraph implementation of Legion's read-only Scout runtime contract."""

from __future__ import annotations

from typing import Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from .scout import (
    MissionContext,
    ScoutEvidence,
    ScoutRequest,
    ScoutResult,
    validate_scout_request,
)


class ScoutResponder(Protocol):
    """Model-provider boundary used by the LangGraph recommendation node."""

    def recommend(
        self,
        *,
        context: MissionContext,
        query: str,
        evidence: tuple[ScoutEvidence, ...],
    ) -> str: ...


class ScoutGraphState(TypedDict):
    request: ScoutRequest
    recommendation: str


class LangGraphScoutRuntime:
    """One-node LangGraph runtime with no tool or Mission-mutation access."""

    def __init__(self, responder: ScoutResponder) -> None:
        self._responder = responder
        builder = StateGraph(ScoutGraphState)
        builder.add_node("recommend", self._recommend)
        builder.add_edge(START, "recommend")
        builder.add_edge("recommend", END)
        self._graph = builder.compile()

    def run_scout(self, request: ScoutRequest) -> ScoutResult:
        validate_scout_request(request)
        state = self._graph.invoke({"request": request})
        recommendation = state["recommendation"]
        if not isinstance(recommendation, str) or not recommendation.strip():
            raise ValueError("SCOUT_RESPONSE_INVALID")
        return ScoutResult(
            mission_id=request.context.mission_id,
            mission_version=request.context.mission_version,
            scout=request.scout,
            query=request.query,
            evidence=request.evidence,
            recommendation=recommendation,
        )

    def _recommend(self, state: ScoutGraphState) -> dict[str, str]:
        request = state["request"]
        return {
            "recommendation": self._responder.recommend(
                context=request.context,
                query=request.query,
                evidence=request.evidence,
            )
        }
