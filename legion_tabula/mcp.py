"""Streamable HTTP transport shared by Legion's Tabula clients."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

_PROTOCOL_VERSION = "2025-06-18"


@dataclass(frozen=True)
class McpResponse:
    """A decoded MCP HTTP response without request credentials."""

    status_code: int
    body: dict[str, Any] | None


@dataclass(frozen=True)
class _HttpResponse:
    status_code: int
    body: dict[str, Any] | None
    session_id: str | None


class McpHttpTransport:
    """Invoke a Tabula MCP tool through a negotiated Streamable HTTP session."""

    def __init__(self, endpoint: str, *, timeout_seconds: float = 10.0) -> None:
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("MCP endpoint must be an HTTP URL")
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._session_id: str | None = None

    def __call__(self, token: str | Callable[[], str], request: dict[str, Any]) -> McpResponse:
        next_token = (lambda: token) if isinstance(token, str) else token
        if self._session_id is None:
            opening = self._post(next_token(), "initialize", {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pantheon-legion", "version": "1.0"},
            })
            if opening.status_code != 200 or not opening.session_id:
                return McpResponse(opening.status_code, opening.body)
            self._session_id = opening.session_id
            initialized = self._post(next_token(), "notifications/initialized", {}, notification=True)
            if initialized.status_code not in {200, 202}:
                return McpResponse(initialized.status_code, initialized.body)
        response = self._post(next_token(), "tools/call", request)
        return McpResponse(response.status_code, response.body)

    def _post(self, token: str, method: str, params: dict[str, Any], *, notification: bool = False) -> _HttpResponse:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notification:
            payload["id"] = str(uuid4())
        headers = {
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if self._session_id is not None:
            headers["MCP-Protocol-Version"] = _PROTOCOL_VERSION
            headers["Mcp-Session-Id"] = self._session_id
        http_request = Request(
            self._endpoint, data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            method="POST", headers=headers,
        )
        try:
            with urlopen(http_request, timeout=self._timeout_seconds) as response:
                return _HttpResponse(response.status, _decode_body(response.read()), response.headers.get("Mcp-Session-Id"))
        except HTTPError as error:
            return _HttpResponse(error.code, _decode_body(error.read()), error.headers.get("Mcp-Session-Id"))


def _sse_payload(text: str) -> dict[str, Any] | None:
    for line in reversed(text.splitlines()):
        if line.startswith("data: "):
            try:
                value = json.loads(line.removeprefix("data: "))
            except json.JSONDecodeError:
                return None
            return value if isinstance(value, dict) else None
    return None


def _decode_body(raw: bytes) -> dict[str, Any] | None:
    """Unwrap FastMCP JSON-RPC structured content without retaining credentials."""
    try:
        text = raw.decode("utf-8")
        payload = json.loads(text)
    except UnicodeDecodeError:
        return None
    except json.JSONDecodeError:
        payload = _sse_payload(text)
        if payload is None:
            return None
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return payload
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    for content in result.get("content", []):
        if isinstance(content, dict) and content.get("type") == "text":
            try:
                decoded = json.loads(content.get("text"))
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(decoded, dict):
                return decoded
    return result
