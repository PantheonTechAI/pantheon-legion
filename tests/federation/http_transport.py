"""HTTP transport for the disposable Tabula Streamable HTTP MCP service."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from .runner import McpReply


class McpHttpTransport:
    """Invoke one real Tabula tool using only the delegated bearer token."""

    def __init__(self, endpoint: str, *, timeout_seconds: float = 10.0) -> None:
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError("MCP endpoint must be an HTTP URL")
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds

    def __call__(self, token: str, request: dict[str, Any]) -> McpReply:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "tools/call",
            "params": request,
        }
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        http_request = Request(
            self._endpoint,
            data=encoded,
            method="POST",
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(http_request, timeout=self._timeout_seconds) as response:
                return McpReply(response.status, _decode_body(response.read()))
        except HTTPError as error:
            return McpReply(error.code, _decode_body(error.read()))


def _decode_body(raw: bytes) -> dict[str, Any] | None:
    """Unwrap FastMCP JSON-RPC structured content without leaking credentials."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")
    if isinstance(result, dict):
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        for content in result.get("content", []):
            if isinstance(content, dict) and content.get("type") == "text":
                text = content.get("text")
                try:
                    decoded = json.loads(text)
                except (TypeError, json.JSONDecodeError):
                    continue
                if isinstance(decoded, dict):
                    return decoded
        return result
    return payload
