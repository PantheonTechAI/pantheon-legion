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

__all__ = [
    "CognitionRuntimeAdapter",
    "ConformanceCheck",
    "InMemoryScoutRuntime",
    "MissionContext",
    "ReadOnlyScoutError",
    "ScoutEvidence",
    "ScoutRequest",
    "ScoutResult",
    "ScoutRuntimeConformance",
    "ScoutRuntimeConformanceReport",
]
