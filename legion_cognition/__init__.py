"""Provider-neutral cognition boundaries for Legion agents."""

from .scout import (
    CognitionRuntimeAdapter,
    InMemoryScoutRuntime,
    MissionContext,
    ReadOnlyScoutError,
    ScoutEvidence,
    ScoutRequest,
    ScoutResult,
)
from .conformance import ConformanceCheck, ScoutRuntimeConformance, ScoutRuntimeConformanceReport
from .langgraph_runtime import LangGraphScoutRuntime, ScoutResponder

__all__ = [
    "CognitionRuntimeAdapter",
    "ConformanceCheck",
    "InMemoryScoutRuntime",
    "LangGraphScoutRuntime",
    "MissionContext",
    "ReadOnlyScoutError",
    "ScoutEvidence",
    "ScoutRequest",
    "ScoutResult",
    "ScoutRuntimeConformance",
    "ScoutRuntimeConformanceReport",
    "ScoutResponder",
]
