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

__all__ = [
    "CognitionRuntimeAdapter",
    "InMemoryScoutRuntime",
    "MissionContext",
    "ReadOnlyScoutError",
    "ScoutEvidence",
    "ScoutRequest",
    "ScoutResult",
]
