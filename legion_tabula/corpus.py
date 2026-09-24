"""Validated client for Tabula's dedicated federated corpus-read tool."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from datetime import datetime
from typing import Any, Callable, Protocol
import re
from urllib.parse import urlparse
from uuid import UUID, uuid4

from .mcp import McpHttpTransport, McpResponse, McpTransportError

_ERROR_CODES = frozenset({"INVALID_REQUEST", "AUTHORIZATION_DENIED", "DEADLINE_EXCEEDED", "SERVICE_UNAVAILABLE", "INTERNAL_ERROR"})
_INTENTS = frozenset({"SCOUT_EVIDENCE", "OPERATOR_CONTEXT"})


class McpTransport(Protocol):
    def __call__(self, token: Callable[[], str], request: dict[str, Any]) -> McpResponse: ...


@dataclass(frozen=True)
class ScopeBinding:
    """A Tabula-owned binding reference; callers cannot select its resources."""

    id: str
    version: str

    def __post_init__(self) -> None:
        _require_uuid(self.id)
        if not _valid_version(self.version):
            raise ValueError("TABULA_BINDING_INVALID")

    def payload(self) -> dict[str, str]:
        return {"id": self.id, "version": self.version}


@dataclass(frozen=True)
class CorpusRecord:
    """Validated corpus data, with content separate from its audit reference."""

    record_id: str
    domain: str
    revision: str
    canonical_uri: str
    citation: str
    source_uri: str | None
    recorded_at: str
    retrieved_at: str
    selection_explanation: str
    content: str | None

    def audit_reference(self) -> dict[str, str]:
        """Safe record identity for Mission audit; excludes content and citation."""
        return {"record_id": self.record_id, "revision": self.revision, "canonical_uri": self.canonical_uri}


@dataclass(frozen=True)
class CorpusRead:
    """A successful correlated Tabula corpus response."""

    request_id: str
    correlation_id: str
    binding: ScopeBinding
    tabula_audit_correlation_id: str
    records: tuple[CorpusRecord, ...]

    def audit_data(self) -> dict[str, Any]:
        """The only response data appropriate for Aquila Mission audit by default."""
        return {
            "tabula_audit_correlation_id": self.tabula_audit_correlation_id,
            "record_references": [record.audit_reference() for record in self.records],
        }


class CorpusReadError(RuntimeError):
    """Safe client failure that never carries credentials or corpus response content."""

    def __init__(self, code: str, *, request_id: str, correlation_id: str, tabula_audit_correlation_id: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.request_id = request_id
        self.correlation_id = correlation_id
        self.tabula_audit_correlation_id = tabula_audit_correlation_id

    def audit_data(self) -> dict[str, str]:
        data = {"error_code": self.code}
        if self.tabula_audit_correlation_id:
            data["tabula_audit_correlation_id"] = self.tabula_audit_correlation_id
        return data


class TabulaCorpusClient:
    """Validate bounded federated search and exact provenance reread contracts."""

    def __init__(self, transport: McpTransport) -> None:
        self._transport = transport

    def read(
        self,
        *,
        token: Callable[[], str],
        binding: ScopeBinding,
        query: str,
        correlation_id: str | None = None,
        intent: str = "SCOUT_EVIDENCE",
        limit: int = 10,
    ) -> CorpusRead:
        if not callable(token) or not isinstance(query, str) or not query.strip() or len(query) > 2000:
            raise ValueError("TABULA_CORPUS_REQUEST_INVALID")
        if intent not in _INTENTS or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise ValueError("TABULA_CORPUS_REQUEST_INVALID")
        correlation = correlation_id or str(uuid4())
        _require_uuid(correlation)
        request_id = str(uuid4())
        for attempt in range(2):
            request = {
                "schema_version": "1.0", "request_id": request_id, "correlation_id": correlation,
                "binding": binding.payload(), "intent": intent, "query": query, "limit": limit,
            }
            try:
                reply = self._transport(token, {"name": "legion_search_corpus", "arguments": request})
            except McpTransportError as error:
                raise CorpusReadError(error.code, request_id=request_id, correlation_id=correlation) from None
            except OSError:
                raise CorpusReadError("SERVICE_UNAVAILABLE", request_id=request_id, correlation_id=correlation) from None
            if reply.status_code == 401:
                raise CorpusReadError("UNAUTHENTICATED", request_id=request_id, correlation_id=correlation)
            if reply.status_code != 200 or not isinstance(reply.body, dict):
                raise CorpusReadError("TABULA_PROTOCOL_ERROR", request_id=request_id, correlation_id=correlation)
            if "code" not in reply.body:
                return _parse_success(reply.body, request_id, correlation, binding, limit)
            error = _parse_error(reply.body, request_id, correlation)
            if error.code == "SERVICE_UNAVAILABLE" and attempt == 0:
                request_id = str(uuid4())
                continue
            raise error
        raise AssertionError("unreachable")

    def reread(self, *, token: Callable[[], str], binding: ScopeBinding,
               references: tuple[CorpusReference, ...], correlation_id: str) -> CorpusRead:
        if (not callable(token) or not isinstance(references, tuple) or not 1 <= len(references) <= 8
                or any(type(ref) is not CorpusReference for ref in references)
                or len({ref.record_id for ref in references}) != len(references)
                or sum(ref.content_bytes for ref in references) > 32768):
            raise ValueError("TABULA_CORPUS_REQUEST_INVALID")
        if isinstance(self._transport, McpHttpTransport) and (
            self._transport.max_response_bytes is None or self._transport.max_response_bytes > 1024 * 1024
        ):
            raise ValueError("TABULA_REREAD_TRANSPORT_UNBOUNDED")
        _require_uuid(correlation_id)
        for attempt in range(2):
            request_id = str(uuid4())
            request = {"schema_version": "1.0", "request_id": request_id,
                       "correlation_id": correlation_id, "binding": binding.payload(),
                       "intent": "SCOUT_EVIDENCE", "projection": "utf8-prefix-v1",
                       "references": [ref.payload() for ref in references]}
            try:
                reply = self._transport(token, {"name": "legion_reread_corpus", "arguments": request})
            except McpTransportError as exc:
                raise CorpusReadError(exc.code, request_id=request_id, correlation_id=correlation_id) from None
            except OSError:
                raise CorpusReadError("SERVICE_UNAVAILABLE", request_id=request_id, correlation_id=correlation_id) from None
            if reply.status_code == 401:
                raise CorpusReadError("UNAUTHENTICATED", request_id=request_id, correlation_id=correlation_id)
            if reply.status_code != 200 or not isinstance(reply.body, dict):
                raise CorpusReadError("TABULA_PROTOCOL_ERROR", request_id=request_id, correlation_id=correlation_id)
            if "code" in reply.body:
                error = _parse_error(reply.body, request_id, correlation_id)
                if error.code == "SERVICE_UNAVAILABLE" and attempt == 0:
                    continue
                raise error
            result = _parse_success(reply.body, request_id, correlation_id, binding, len(references))
            try:
                if len(result.records) != len(references):
                    raise ValueError
                for record, ref in zip(result.records, references, strict=True):
                    raw = record.content.encode("utf-8") if isinstance(record.content, str) else b""
                    if ((record.record_id, record.revision, record.canonical_uri) !=
                            (ref.record_id, ref.revision, ref.canonical_uri)
                            or len(raw) != ref.content_bytes or sha256(raw).hexdigest() != ref.content_sha256):
                        raise ValueError
            except (ValueError, TypeError, UnicodeError):
                raise CorpusReadError("TABULA_PROTOCOL_ERROR", request_id=request_id,
                                      correlation_id=correlation_id,
                                      tabula_audit_correlation_id=result.tabula_audit_correlation_id) from None
            return result
        raise AssertionError("unreachable")


@dataclass(frozen=True)
class CorpusReference:
    record_id: str
    revision: str
    canonical_uri: str
    content_bytes: int
    content_sha256: str

    def __post_init__(self):
        for value, maximum in ((self.record_id, 512), (self.revision, 128), (self.canonical_uri, 2048)):
            if not isinstance(value, str) or not 1 <= len(value) <= maximum:
                raise ValueError("TABULA_CORPUS_REFERENCE_INVALID")
            value.encode("utf-8")
        _require_uri(self.canonical_uri)
        if (type(self.content_bytes) is not int or not 1 <= self.content_bytes <= 8192
                or not isinstance(self.content_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.content_sha256)):
            raise ValueError("TABULA_CORPUS_REFERENCE_INVALID")

    def payload(self):
        return {"record_id": self.record_id, "revision": self.revision,
                "content_bytes": self.content_bytes, "content_sha256": self.content_sha256}


def _parse_success(body: dict[str, Any], request_id: str, correlation_id: str, binding: ScopeBinding, limit: int) -> CorpusRead:
    required = {"schema_version", "request_id", "correlation_id", "binding", "results", "tabula_audit_correlation_id"}
    if set(body) != required or body.get("schema_version") != "1.0":
        raise CorpusReadError("TABULA_PROTOCOL_ERROR", request_id=request_id, correlation_id=correlation_id)
    if body["request_id"] != request_id or body["correlation_id"] != correlation_id or body["binding"] != binding.payload():
        raise CorpusReadError("TABULA_PROTOCOL_ERROR", request_id=request_id, correlation_id=correlation_id)
    try:
        _require_uuid(body["tabula_audit_correlation_id"])
        if not isinstance(body["results"], list) or len(body["results"]) > limit:
            raise ValueError
        records = tuple(_parse_record(value) for value in body["results"])
    except (KeyError, TypeError, ValueError):
        raise CorpusReadError("TABULA_PROTOCOL_ERROR", request_id=request_id, correlation_id=correlation_id) from None
    return CorpusRead(request_id, correlation_id, binding, body["tabula_audit_correlation_id"], records)


def _parse_error(body: dict[str, Any], request_id: str, correlation_id: str) -> CorpusReadError:
    required = {"schema_version", "request_id", "correlation_id", "code", "retryable", "tabula_audit_correlation_id"}
    allowed = required | {"message", "retry_after_ms"}
    try:
        if not required.issubset(body) or not set(body).issubset(allowed) or body["schema_version"] != "1.0":
            raise ValueError
        if body["request_id"] != request_id or body["correlation_id"] != correlation_id or body["code"] not in _ERROR_CODES:
            raise ValueError
        if not isinstance(body["retryable"], bool):
            raise ValueError
        _require_uuid(body["tabula_audit_correlation_id"])
        if body["code"] == "SERVICE_UNAVAILABLE":
            if body["retryable"] is not True or not isinstance(body.get("retry_after_ms"), int) or isinstance(body.get("retry_after_ms"), bool):
                raise ValueError
        elif body["retryable"] or "retry_after_ms" in body:
            raise ValueError
    except (TypeError, ValueError):
        return CorpusReadError("TABULA_PROTOCOL_ERROR", request_id=request_id, correlation_id=correlation_id)
    return CorpusReadError(body["code"], request_id=request_id, correlation_id=correlation_id, tabula_audit_correlation_id=body["tabula_audit_correlation_id"])


def _parse_record(value: Any) -> CorpusRecord:
    required = {"record_id", "domain", "revision", "canonical_uri", "source", "recorded_at", "retrieved_at", "selection_explanation"}
    allowed = required | {"content"}
    if not isinstance(value, dict) or set(value) - allowed or not required.issubset(value):
        raise ValueError
    source = value["source"]
    if not isinstance(source, dict) or set(source) - {"citation", "uri"} or not isinstance(source.get("citation"), str) or not source["citation"] or len(source["citation"]) > 4000:
        raise ValueError
    for key, maximum in (("record_id", 512), ("domain", 64), ("revision", 128), ("canonical_uri", 2048), ("recorded_at", 64), ("retrieved_at", 64), ("selection_explanation", 2000)):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > maximum:
            raise ValueError
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value["domain"]):
        raise ValueError
    _require_uri(value["canonical_uri"])
    _require_timestamp(value["recorded_at"])
    _require_timestamp(value["retrieved_at"])
    source_uri = source.get("uri")
    if source_uri is not None:
        if not isinstance(source_uri, str) or len(source_uri) > 2048:
            raise ValueError
        _require_uri(source_uri)
    content = value.get("content")
    if content is not None and (not isinstance(content, str) or len(content) > 20000):
        raise ValueError
    return CorpusRecord(value["record_id"], value["domain"], value["revision"], value["canonical_uri"], source["citation"], source_uri, value["recorded_at"], value["retrieved_at"], value["selection_explanation"], content)


def _require_uuid(value: Any) -> None:
    if not isinstance(value, str):
        raise ValueError
    UUID(value)


def _require_uri(value: str) -> None:
    if not urlparse(value).scheme:
        raise ValueError


def _require_timestamp(value: str) -> None:
    datetime.fromisoformat(value.replace("Z", "+00:00"))


def _valid_version(value: Any) -> bool:
    parts = value.split(".") if isinstance(value, str) else []
    return len(parts) == 3 and all(part.isdigit() and part for part in parts)
