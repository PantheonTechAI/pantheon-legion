"""Static capability resources; no scheduling or workload authority."""

from .inference import (
    ComputeNode, EndpointObservation, InferenceEndpoint,
    InferenceTopologyCatalog, NodeObservation,
)

__all__ = [
    "ComputeNode", "EndpointObservation", "InferenceEndpoint",
    "InferenceTopologyCatalog", "NodeObservation",
]
