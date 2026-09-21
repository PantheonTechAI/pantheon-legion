"""Live scenario matrix for a preflight-approved disposable Tabula stack."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable
from uuid import UUID, uuid4

from legion_tabula import (
    CorpusReadError,
    McpHttpTransport,
    McpResponse,
    RegistryReadError,
    ScopeBinding,
    TabulaCorpusClient,
    TabulaRegistryClient,
)

from .fixture_server import FixtureSTSServer
from .runner import ConformanceResult, FederatedConformanceRunner, _claims


_ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"
_WORKSPACE_ID = "22222222-2222-4222-8222-222222222222"
_CORPUS_BINDING_ID = "33333333-3333-4333-8333-333333333333"
_REGISTRY_BINDING_ID = "44444444-4444-4444-8444-444444444444"
_SUSPENDED_BINDING_ID = "55555555-5555-4555-8555-555555555555"
_REVOKED_BINDING_ID = "66666666-6666-4666-8666-666666666666"
_EXPIRED_BINDING_ID = "77777777-7777-4777-8777-777777777777"


@dataclass(frozen=True)
class DisposableRun:
    """Only a callback that has already passed Tabula's isolation preflight may start a stack."""

    mcp_endpoint: str
    start_stack: Callable[[str], None]
    transport_factory: Callable[[str], Callable] = McpHttpTransport
    restart_stack: Callable[[], None] | None = None
    exercise_live_faults: bool = False


def run_disposable_conformance(run: DisposableRun) -> tuple[ConformanceResult, ...]:
    """Start fixture STS, invoke the preflight-approved stack, and run the v1 matrix."""
    with FixtureSTSServer(host="0.0.0.0") as sts:
        run.start_stack(sts.docker_introspection_url)
        issue_token = lambda claims: sts.issue_token(
            _claims_at(claims, sts.current_time)
        )
        runner = FederatedConformanceRunner(issue_token, run.transport_factory(run.mcp_endpoint))
        corpus = _arguments(_CORPUS_BINDING_ID, "SCOUT_EVIDENCE")
        registry = _arguments(_REGISTRY_BINDING_ID, "SCOUT_DISCOVERY")
        suspended = _arguments(_SUSPENDED_BINDING_ID, "SCOUT_EVIDENCE")
        revoked = _arguments(_REVOKED_BINDING_ID, "SCOUT_EVIDENCE")
        expired = _arguments(_EXPIRED_BINDING_ID, "SCOUT_EVIDENCE")
        results = [
            runner.success("corpus-success", "TABULA_CORPUS_READ", "legion_search_corpus", corpus),
            runner.success("registry-success", "TABULA_REGISTRY_READ", "legion_discover_registry", registry),
            _corpus_client_success(sts, run, corpus),
            _registry_client_success(sts, run, registry),
            runner.pre_tool_denial("invalid-token", "not-a-delegated-token", "legion_search_corpus", corpus),
            runner.post_auth_denial("suspended-binding", "TABULA_CORPUS_READ", "legion_search_corpus", suspended),
        ]
        if run.exercise_live_faults:
            results.extend(
                (
                    _corpus_client_timeout(sts, run, corpus),
                    _corpus_client_malformed_response(sts, run, corpus),
                    _corpus_client_retry(sts, run, corpus),
                )
            )
        revoked_token = issue_token(_claims("TABULA_CORPUS_READ", revoked))
        sts.revoke_binding(_REVOKED_BINDING_ID)
        results.append(runner.pre_tool_denial("revoked-token", revoked_token, "legion_search_corpus", revoked))
        if run.restart_stack is not None:
            run.restart_stack()
            results.append(
                _corpus_client_success(
                    sts,
                    run,
                    _arguments(_CORPUS_BINDING_ID, "SCOUT_EVIDENCE"),
                    scenario_id="corpus-after-service-restart",
                )
            )
        expired_token = issue_token(_claims("TABULA_CORPUS_READ", expired))
        sts.advance(timedelta(minutes=6))
        results.append(runner.pre_tool_denial("expired-token", expired_token, "legion_search_corpus", expired))
    return tuple(results)


def _corpus_client_success(
    sts: FixtureSTSServer,
    run: DisposableRun,
    arguments: dict[str, object],
    *,
    scenario_id: str = "corpus-client-success",
) -> ConformanceResult:
    try:
        result = TabulaCorpusClient(run.transport_factory(run.mcp_endpoint)).read(
            token=lambda: sts.issue_token(
                _claims(
                    "TABULA_CORPUS_READ",
                    arguments,
                    now=sts.current_time,
                )
            ),
            binding=ScopeBinding(**arguments["binding"]), query=str(arguments["query"]),
            correlation_id=str(arguments["correlation_id"]), intent=str(arguments["intent"]),
            limit=int(arguments["limit"]),
        )
    except (CorpusReadError, ValueError) as error:
        return ConformanceResult(scenario_id, False, f"client failed: {error}")
    return ConformanceResult(
        scenario_id, result.correlation_id == arguments["correlation_id"],
        "validated corpus client response",
    )


def _registry_client_success(sts: FixtureSTSServer, run: DisposableRun, arguments: dict[str, object]) -> ConformanceResult:
    try:
        result = TabulaRegistryClient(run.transport_factory(run.mcp_endpoint)).discover(
            token=lambda: sts.issue_token(
                _claims(
                    "TABULA_REGISTRY_READ",
                    arguments,
                    now=sts.current_time,
                )
            ),
            binding=ScopeBinding(**arguments["binding"]), query=str(arguments["query"]),
            correlation_id=str(arguments["correlation_id"]), intent=str(arguments["intent"]),
            limit=int(arguments["limit"]),
        )
    except (RegistryReadError, ValueError) as error:
        return ConformanceResult("registry-client-success", False, f"client failed: {error}")
    return ConformanceResult(
        "registry-client-success", result.correlation_id == arguments["correlation_id"],
        "validated Registry client response",
    )


def _corpus_client_timeout(
    sts: FixtureSTSServer,
    run: DisposableRun,
    arguments: dict[str, object],
) -> ConformanceResult:
    """Prove the real HTTP boundary converts an exhausted deadline to a safe code."""
    try:
        TabulaCorpusClient(
            McpHttpTransport(run.mcp_endpoint, timeout_seconds=1e-12)
        ).read(
            token=_token_supplier(sts, arguments),
            binding=ScopeBinding(**arguments["binding"]),
            query=str(arguments["query"]),
            correlation_id=str(arguments["correlation_id"]),
            intent=str(arguments["intent"]),
            limit=int(arguments["limit"]),
        )
    except CorpusReadError as error:
        return ConformanceResult(
            "corpus-client-timeout",
            error.code == "DEADLINE_EXCEEDED",
            f"safe client error: {error.code}",
        )
    return ConformanceResult("corpus-client-timeout", False, "client unexpectedly succeeded")


def _corpus_client_malformed_response(
    sts: FixtureSTSServer,
    run: DisposableRun,
    arguments: dict[str, object],
) -> ConformanceResult:
    """Corrupt a real successful response at Legion's edge and require fail-closed parsing."""
    live_transport = run.transport_factory(run.mcp_endpoint)

    def malformed(token, request):
        reply = live_transport(token, request)
        body = dict(reply.body or {})
        body["unexpected"] = "injected-at-client-edge"
        return McpResponse(reply.status_code, body)

    try:
        TabulaCorpusClient(malformed).read(
            token=_token_supplier(sts, arguments),
            binding=ScopeBinding(**arguments["binding"]),
            query=str(arguments["query"]),
            correlation_id=str(arguments["correlation_id"]),
            intent=str(arguments["intent"]),
            limit=int(arguments["limit"]),
        )
    except CorpusReadError as error:
        return ConformanceResult(
            "corpus-client-malformed-response",
            error.code == "TABULA_PROTOCOL_ERROR",
            f"safe client error: {error.code}",
        )
    return ConformanceResult(
        "corpus-client-malformed-response", False, "client accepted malformed response"
    )


def _corpus_client_retry(
    sts: FixtureSTSServer,
    run: DisposableRun,
    arguments: dict[str, object],
) -> ConformanceResult:
    """Inject one retryable edge response after a real call, then succeed live."""
    live_transport = run.transport_factory(run.mcp_endpoint)
    requests: list[dict[str, object]] = []

    def unavailable_once(token, request):
        reply = live_transport(token, request)
        request_arguments = dict(request["arguments"])
        requests.append(request_arguments)
        if len(requests) == 1:
            return McpResponse(
                200,
                {
                    "schema_version": "1.0",
                    "request_id": request_arguments["request_id"],
                    "correlation_id": request_arguments["correlation_id"],
                    "code": "SERVICE_UNAVAILABLE",
                    "retryable": True,
                    "retry_after_ms": 1,
                    "tabula_audit_correlation_id": str(uuid4()),
                },
            )
        return reply

    try:
        result = TabulaCorpusClient(unavailable_once).read(
            token=_token_supplier(sts, arguments),
            binding=ScopeBinding(**arguments["binding"]),
            query=str(arguments["query"]),
            correlation_id=str(arguments["correlation_id"]),
            intent=str(arguments["intent"]),
            limit=int(arguments["limit"]),
        )
    except (CorpusReadError, ValueError) as error:
        return ConformanceResult("corpus-client-retry", False, f"client failed: {error}")
    passed = (
        len(requests) == 2
        and requests[0]["request_id"] != requests[1]["request_id"]
        and requests[0]["correlation_id"] == requests[1]["correlation_id"]
        and result.request_id == requests[1]["request_id"]
    )
    return ConformanceResult(
        "corpus-client-retry", passed, "bounded retry with fresh request id"
    )


def _token_supplier(sts: FixtureSTSServer, arguments: dict[str, object]):
    return lambda: sts.issue_token(
        _claims(
            "TABULA_CORPUS_READ",
            arguments,
            now=sts.current_time,
        )
    )


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


def _claims_at(claims: dict[str, object], now) -> dict[str, object]:
    return {
        **claims,
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=5))
        .isoformat()
        .replace("+00:00", "Z"),
    }
