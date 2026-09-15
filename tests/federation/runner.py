"""Reusable scenarios for the real Legion--Tabula federated conformance run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4



@dataclass(frozen=True)
class McpReply:
    status_code: int
    body: dict[str, Any] | None


@dataclass(frozen=True)
class ConformanceResult:
    scenario_id: str
    passed: bool
    detail: str


class FederatedConformanceRunner:
    """Exercise an injected real MCP transport with fresh fixture tokens."""

    def __init__(self, issue_token: Callable[[dict[str, Any]], str], call_mcp: Callable[[Callable[[], str], dict[str, Any]], McpReply]) -> None:
        self._issue_token = issue_token
        self._call_mcp = call_mcp

    def success(self, scenario_id: str, operation: str, tool: str, arguments: dict[str, Any]) -> ConformanceResult:
        reply = self._call_mcp(lambda: self._issue_token(_claims(operation, arguments)), {"name": tool, "arguments": _mcp_arguments(arguments)})
        body = reply.body or {}
        passed = (
            reply.status_code == 200
            and "code" not in body
            and body.get("schema_version") == "1.0"
            and body.get("request_id") == arguments["request_id"]
            and body.get("correlation_id") == arguments["correlation_id"]
            and "tabula_audit_correlation_id" in body
        )
        return ConformanceResult(scenario_id, passed, "success response" if passed else _unexpected(reply))

    def pre_tool_denial(self, scenario_id: str, token: str, tool: str, arguments: dict[str, Any]) -> ConformanceResult:
        reply = self._call_mcp(lambda: token, {"name": tool, "arguments": _mcp_arguments(arguments)})
        passed = reply.status_code == 401 and reply.body is not None and "tabula_audit_correlation_id" not in reply.body
        return ConformanceResult(scenario_id, passed, "generic pre-tool 401" if passed else _unexpected(reply))

    def post_auth_denial(self, scenario_id: str, operation: str, tool: str, arguments: dict[str, Any]) -> ConformanceResult:
        reply = self._call_mcp(lambda: self._issue_token(_claims(operation, arguments)), {"name": tool, "arguments": _mcp_arguments(arguments)})
        body = reply.body or {}
        passed = reply.status_code == 200 and body.get("code") == "AUTHORIZATION_DENIED" and body.get("retryable") is False and "tabula_audit_correlation_id" in body
        return ConformanceResult(scenario_id, passed, "non-disclosing post-auth denial" if passed else _unexpected(reply))

    def retry(self, scenario_id: str, operation: str, tool: str, arguments: dict[str, Any], retry_arguments: dict[str, Any]) -> ConformanceResult:
        first = self._call_mcp(lambda: self._issue_token(_claims(operation, arguments)), {"name": tool, "arguments": _mcp_arguments(arguments)})
        second = self._call_mcp(lambda: self._issue_token(_claims(operation, retry_arguments)), {"name": tool, "arguments": _mcp_arguments(retry_arguments)})
        first_body, second_body = first.body or {}, second.body or {}
        passed = (
            first.status_code == 200 and first_body.get("code") == "SERVICE_UNAVAILABLE" and first_body.get("retryable") is True
            and second.status_code == 200 and second_body.get("schema_version") == "1.0"
            and arguments["correlation_id"] == retry_arguments["correlation_id"]
            and arguments["request_id"] != retry_arguments["request_id"]
        )
        return ConformanceResult(scenario_id, passed, "bounded retry" if passed else "retry contract failed")


def _unexpected(reply: McpReply) -> str:
    body = reply.body or {}
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    code = body.get("code") or error.get("code") or "unclassified"
    return f"unexpected reply: {reply.status_code} {code}"


def _mcp_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in arguments.items() if key not in {"organization_id", "workspace_id"}}


def _claims(operation: str, arguments: dict[str, Any]) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    binding = arguments["binding"]
    return {
        "schema_version": "1.0", "assertion_id": str(uuid4()), "issuer": "aquila", "audience": "pantheon-sts",
        "subject_id": "federation-scout", "actor_id": "aquila", "mission_id": str(uuid4()),
        "organization_id": arguments["organization_id"], "workspace_id": arguments["workspace_id"],
        "target_product": "TABULA", "target_audience": "pantheon-tabula-mcp", "operation": operation,
        "binding_id": binding["id"], "binding_version": binding["version"],
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "correlation_id": arguments["correlation_id"],
    }
