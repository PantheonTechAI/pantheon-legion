"""Immutable, operator-configured compute nodes and inference endpoints."""

from dataclasses import dataclass
from datetime import datetime
import math
import re
from urllib.parse import urlsplit


def identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}", value):
        raise ValueError("INVALID_IDENTIFIER")


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed
    except (ValueError, TypeError, AttributeError):
        raise ValueError("INVALID_TIMESTAMP") from None


def positive(value: int) -> None:
    if type(value) is not int or not 1 <= value <= 2**31 - 1:
        raise ValueError("INVALID_POSITIVE_INTEGER")


def enabled_flag(value: bool) -> None:
    if type(value) is not bool:
        raise ValueError("INVALID_ENABLED_FLAG")


def distinct_records(records: tuple, record_type: type, key: str) -> None:
    if not isinstance(records, tuple) or not all(type(item) is record_type for item in records):
        raise ValueError("INVALID_CATALOG_RECORDS")
    if len({getattr(item, key) for item in records}) != len(records):
        raise ValueError("DUPLICATE_CATALOG_IDENTITY")


@dataclass(frozen=True)
class ComputeNode:
    node_id: str
    locality: str
    trust_zone: str
    enabled: bool = True

    def __post_init__(self):
        identifier(self.node_id)
        identifier(self.trust_zone)
        if self.locality not in {"LOCAL", "REMOTE"}:
            raise ValueError("INVALID_LOCALITY")
        enabled_flag(self.enabled)


@dataclass(frozen=True)
class InferenceEndpoint:
    endpoint_id: str
    node_id: str
    origin: str
    enabled: bool = True

    def __post_init__(self):
        identifier(self.endpoint_id)
        identifier(self.node_id)
        enabled_flag(self.enabled)
        try:
            if not isinstance(self.origin, str) or len(self.origin) > 2048:
                raise ValueError
            if any(ord(c) <= 32 or ord(c) >= 127 for c in self.origin) or "\\" in self.origin:
                raise ValueError
            parsed = urlsplit(self.origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.path not in {"", "/"} or "?" in self.origin or "#" in self.origin
                    or parsed.port == 0):
                raise ValueError
        except (ValueError, TypeError):
            raise ValueError("INVALID_ENDPOINT_ORIGIN") from None


@dataclass(frozen=True)
class InferenceTopologyCatalog:
    catalog_revision: str
    nodes: tuple[ComputeNode, ...]
    endpoints: tuple[InferenceEndpoint, ...]

    def __post_init__(self):
        identifier(self.catalog_revision)
        distinct_records(self.nodes, ComputeNode, "node_id")
        distinct_records(self.endpoints, InferenceEndpoint, "endpoint_id")
        for endpoint in self.endpoints:
            self.resolve_node(endpoint.node_id)

    def resolve_node(self, node_id: str) -> ComputeNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise ValueError("UNKNOWN_COMPUTE_NODE")

    def resolve_endpoint(self, endpoint_id: str) -> InferenceEndpoint:
        for endpoint in self.endpoints:
            if endpoint.endpoint_id == endpoint_id:
                return endpoint
        raise ValueError("UNKNOWN_INFERENCE_ENDPOINT")


def observation(identity, metric, value, unit, measured_at, note, allowed):
    identifier(identity)
    identifier(unit)
    timestamp(measured_at)
    if metric not in allowed or type(value) not in {float, int} or not math.isfinite(value) or value < 0:
        raise ValueError("INVALID_SCOPED_OBSERVATION")
    if not isinstance(note, str) or len(note.encode("utf-8")) > 1024:
        raise ValueError("INVALID_OBSERVATION_NOTE")


@dataclass(frozen=True)
class NodeObservation:
    node_id: str
    metric: str
    value: float
    unit: str
    measured_at: str
    benchmark_note: str = ""

    def __post_init__(self):
        observation(self.node_id, self.metric, self.value, self.unit, self.measured_at,
                    self.benchmark_note, {"memory_capacity", "compute_capacity"})


@dataclass(frozen=True)
class EndpointObservation:
    endpoint_id: str
    metric: str
    value: float
    unit: str
    measured_at: str
    benchmark_note: str = ""

    def __post_init__(self):
        observation(self.endpoint_id, self.metric, self.value, self.unit, self.measured_at,
                    self.benchmark_note, {"healthy", "reachable", "queue_depth", "active_requests"})
