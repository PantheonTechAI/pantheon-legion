"""Live scenario matrix for a preflight-approved disposable Tabula stack."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID, uuid4

from .fixture_server import FixtureSTSServer
from .http_transport import McpHttpTransport
from .runner import ConformanceResult, FederatedConformanceRunner


_ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"
_WORKSPACE_ID = "22222222-2222-4222-8222-222222222222"
_CORPUS_BINDING_ID = "33333333-3333-4333-8333-333333333333"
_REGISTRY_BINDING_ID = "44444444-4444-4444-8444-444444444444"
_SUSPENDED_BINDING_ID = "55555555-5555-4555-8555-555555555555"


@dataclass(frozen=True)
class DisposableRun:
    """Only a callback that has already passed Tabula's isolation preflight may start a stack."""

    mcp_endpoint: str
    start_stack: Callable[[str], None]
    transport_factory: Callable[[str], Callable] = McpHttpTransport


def run_disposable_conformance(run: DisposableRun) -> tuple[ConformanceResult, ...]:
    """Start fixture STS, invoke the preflight-approved stack, and run the v1 matrix."""
    with FixtureSTSServer(host="0.0.0.0") as sts:
        run.start_stack(sts.docker_introspection_url)
        runner = FederatedConformanceRunner(sts.issue_token, run.transport_factory(run.mcp_endpoint))
        corpus = _arguments(_CORPUS_BINDING_ID, "SCOUT_EVIDENCE")
        registry = _arguments(_REGISTRY_BINDING_ID, "SCOUT_DISCOVERY")
        suspended = _arguments(_SUSPENDED_BINDING_ID, "SCOUT_EVIDENCE")
        results = (
            runner.success("corpus-success", "TABULA_CORPUS_READ", "legion_search_corpus", corpus),
            runner.success("registry-success", "TABULA_REGISTRY_READ", "legion_discover_registry", registry),
            runner.pre_tool_denial("invalid-token", "not-a-delegated-token", "legion_search_corpus", corpus),
            runner.post_auth_denial("suspended-binding", "TABULA_CORPUS_READ", "legion_search_corpus", suspended),
        )
    return results


def _arguments(binding_id: str, intent: str) -> dict[str, object]:
    UUID(binding_id)
    return {
        "organization_id": _ORGANIZATION_ID,
        "workspace_id": _WORKSPACE_ID,
        "binding": {"id": binding_id, "version": "1.0.0"},
        "schema_version": "1.0",
        "request_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "intent": intent,
        "query": "least privilege authorization boundary",
        "limit": 1,
    }
