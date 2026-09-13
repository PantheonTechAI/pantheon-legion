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
from .model_provider import (
    ModelInvocationError,
    ModelInvocationProvenance,
    ModelInvocationRequest,
    ModelInvocationResponse,
    ModelProvider,
    ModelProviderScoutResponder,
    ModelProviderTimeout,
    ModelRecommendation,
    ScoutInputRedactor,
    ScoutInvocationPolicy,
)

__all__ = [
    "CognitionRuntimeAdapter",
    "ConformanceCheck",
    "InMemoryScoutRuntime",
    "LangGraphScoutRuntime",
    "ModelInvocationError",
    "ModelInvocationProvenance",
    "ModelInvocationRequest",
    "ModelInvocationResponse",
    "ModelProvider",
    "ModelProviderScoutResponder",
    "ModelProviderTimeout",
    "ModelRecommendation",
    "MissionContext",
    "ReadOnlyScoutError",
    "ScoutEvidence",
    "ScoutInputRedactor",
    "ScoutInvocationPolicy",
    "ScoutRequest",
    "ScoutResult",
    "ScoutRuntimeConformance",
    "ScoutRuntimeConformanceReport",
    "ScoutResponder",
]
