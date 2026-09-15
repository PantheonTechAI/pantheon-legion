"""Validated client for Tabula's dedicated federated Registry-discovery tool."""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import UUID, uuid4
from .corpus import McpTransport, ScopeBinding, _parse_error

_INTENTS = frozenset({"SCOUT_DISCOVERY", "OPERATOR_DISCOVERY"})

@dataclass(frozen=True)
class RegistryEntity:
    entity_id: str
    kind: str
    version: str
    lifecycle_state: str
    validation_result: str
    artifact_hash: str | None
    artifact_uri: str | None
    def audit_reference(self) -> dict[str, str | None]:
        return {"entity_id": self.entity_id, "version": self.version, "lifecycle_state": self.lifecycle_state, "validation_result": self.validation_result, "artifact_hash": self.artifact_hash, "artifact_uri": self.artifact_uri}

@dataclass(frozen=True)
class RegistryDiscovery:
    request_id: str
    correlation_id: str
    binding: ScopeBinding
    tabula_audit_correlation_id: str
    entities: tuple[RegistryEntity, ...]
    def audit_data(self) -> dict[str, Any]:
        return {"tabula_audit_correlation_id": self.tabula_audit_correlation_id, "registry_references": [entity.audit_reference() for entity in self.entities]}

class RegistryReadError(RuntimeError):
    def __init__(self, code: str, *, request_id: str, correlation_id: str, tabula_audit_correlation_id: str | None = None) -> None:
        super().__init__(code); self.code = code; self.request_id = request_id; self.correlation_id = correlation_id; self.tabula_audit_correlation_id = tabula_audit_correlation_id
    def audit_data(self) -> dict[str, str]:
        result = {"error_code": self.code}
        if self.tabula_audit_correlation_id: result["tabula_audit_correlation_id"] = self.tabula_audit_correlation_id
        return result

class TabulaRegistryClient:
    """Calls only discovery; its return value never grants execution authority."""
    def __init__(self, transport: McpTransport) -> None: self._transport = transport
    def discover(self, *, token: Callable[[], str], binding: ScopeBinding, query: str, correlation_id: str | None = None, intent: str = "SCOUT_DISCOVERY", limit: int = 10) -> RegistryDiscovery:
        if not callable(token) or not isinstance(query, str) or not query.strip() or len(query) > 2000 or intent not in _INTENTS or not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50: raise ValueError("TABULA_REGISTRY_REQUEST_INVALID")
        correlation = correlation_id or str(uuid4())
        try: UUID(correlation)
        except (ValueError, TypeError): raise ValueError("TABULA_REGISTRY_REQUEST_INVALID") from None
        request_id = str(uuid4())
        for attempt in range(2):
            args = {"schema_version": "1.0", "request_id": request_id, "correlation_id": correlation, "binding": binding.payload(), "intent": intent, "query": query, "limit": limit}
            try: reply = self._transport(token, {"name": "legion_discover_registry", "arguments": args})
            except OSError: raise RegistryReadError("SERVICE_UNAVAILABLE", request_id=request_id, correlation_id=correlation) from None
            if reply.status_code == 401: raise RegistryReadError("UNAUTHENTICATED", request_id=request_id, correlation_id=correlation)
            if reply.status_code != 200 or not isinstance(reply.body, dict): raise RegistryReadError("TABULA_PROTOCOL_ERROR", request_id=request_id, correlation_id=correlation)
            if "code" not in reply.body: return _success(reply.body, request_id, correlation, binding, limit)
            error = _parse_error(reply.body, request_id, correlation)
            if error.code == "SERVICE_UNAVAILABLE" and attempt == 0: request_id = str(uuid4()); continue
            raise RegistryReadError(error.code, request_id=error.request_id, correlation_id=error.correlation_id, tabula_audit_correlation_id=error.tabula_audit_correlation_id)
        raise AssertionError

def _success(body: dict[str, Any], request_id: str, correlation_id: str, binding: ScopeBinding, limit: int) -> RegistryDiscovery:
    required = {"schema_version", "request_id", "correlation_id", "binding", "results", "tabula_audit_correlation_id"}
    try:
        if set(body) != required or body["schema_version"] != "1.0" or body["request_id"] != request_id or body["correlation_id"] != correlation_id or body["binding"] != binding.payload() or not isinstance(body["results"], list) or len(body["results"]) > limit: raise ValueError
        UUID(body["tabula_audit_correlation_id"])
        entities = tuple(_entity(value) for value in body["results"])
    except (KeyError, TypeError, ValueError): raise RegistryReadError("TABULA_PROTOCOL_ERROR", request_id=request_id, correlation_id=correlation_id) from None
    return RegistryDiscovery(request_id, correlation_id, binding, body["tabula_audit_correlation_id"], entities)

def _entity(value: Any) -> RegistryEntity:
    required = {"entity_id", "kind", "version", "lifecycle_state", "validation_result"}; allowed = required | {"artifact_hash", "artifact_uri"}
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - allowed: raise ValueError
    if not all(isinstance(value[key], str) and value[key] for key in required): raise ValueError
    if len(value["entity_id"]) > 512 or len(value["version"]) > 128 or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value["kind"]): raise ValueError
    if value["lifecycle_state"] not in {"ACTIVE", "DEPRECATED", "RETIRED"} or value["validation_result"] not in {"VALID", "WARNING", "INVALID"}: raise ValueError
    artifact_hash, artifact_uri = value.get("artifact_hash"), value.get("artifact_uri")
    if artifact_hash is None and artifact_uri is None: raise ValueError
    if artifact_hash is not None and (not isinstance(artifact_hash, str) or not re.fullmatch(r"[A-Fa-f0-9]{64}", artifact_hash)): raise ValueError
    if artifact_uri is not None and (not isinstance(artifact_uri, str) or len(artifact_uri) > 2048 or not urlparse(artifact_uri).scheme): raise ValueError
    return RegistryEntity(value["entity_id"], value["kind"], value["version"], value["lifecycle_state"], value["validation_result"], artifact_hash, artifact_uri)
