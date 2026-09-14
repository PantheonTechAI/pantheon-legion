"""Opaque delegated-token service used by the federated-read conformance run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
import secrets
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID, uuid4

from .assertions import AssertionVerificationError

_SCHEMA_VERSION = "1.0"
_STS_AUDIENCE = "pantheon-sts"
_TABULA_AUDIENCE = "pantheon-tabula-mcp"
_OPERATIONS = {"TABULA_CORPUS_READ", "TABULA_REGISTRY_READ"}
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_MAX_TOKEN_LIFETIME = timedelta(minutes=5)
_CLOCK_SKEW = timedelta(seconds=30)


class AssertionVerifier(Protocol):
    def verify(self, compact_assertion: str) -> dict[str, Any]: ...


class STSError(ValueError):
    """Safe STS error: callers must never include a credential in a response."""


@dataclass(frozen=True)
class IssuedToken:
    token: str
    token_id: str
    issued_at: str
    expires_at: str
    authorization_assertion_id: str

    def response(self) -> dict[str, str]:
        return {
            "token": self.token, "token_id": self.token_id, "issued_at": self.issued_at,
            "expires_at": self.expires_at, "authorization_assertion_id": self.authorization_assertion_id,
        }


@dataclass(frozen=True)
class STSAuditEvent:
    event_type: str
    occurred_at: str
    token_id: str | None = None
    authorization_assertion_id: str | None = None
    correlation_id: str | None = None
    mission_id: str | None = None
    binding_id: str | None = None
    operation: str | None = None
    outcome: str = "ALLOWED"


@dataclass
class _TokenRecord:
    token_id: str
    token_hash: str
    claims: dict[str, str]
    expires_at: datetime
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None


class InMemorySecurityTokenService:
    """Deterministic one-time-token STS fixture with redacted audit facts."""

    def __init__(self, verifier: AssertionVerifier, *, now: Callable[[], datetime] | None = None) -> None:
        self._verifier = verifier
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._used_assertions: set[str] = set()
        self._tokens_by_hash: dict[str, _TokenRecord] = {}
        self._tokens_by_id: dict[str, _TokenRecord] = {}
        self.audit_events: list[STSAuditEvent] = []

    def issue(self, compact_assertion: str) -> IssuedToken:
        try:
            claims = self._validate_claims(self._verifier.verify(compact_assertion))
        except (AssertionVerificationError, STSError):
            self._record("ASSERTION_REJECTED", outcome="DENIED")
            raise STSError("assertion rejected")
        assertion_id = claims["assertion_id"]
        if assertion_id in self._used_assertions:
            self._record("ASSERTION_REPLAYED", claims, outcome="DENIED")
            raise STSError("assertion rejected")
        self._used_assertions.add(assertion_id)
        token = f"pts_{secrets.token_urlsafe(32)}"
        token_id = str(uuid4())
        record = _TokenRecord(token_id, self._hash(token), claims, self._parse_time(claims["expires_at"]))
        self._tokens_by_hash[record.token_hash] = record
        self._tokens_by_id[record.token_id] = record
        self._record("TOKEN_ISSUED", claims, token_id=token_id)
        return IssuedToken(token, token_id, self._format_time(self._current_time()), claims["expires_at"], assertion_id)

    def introspect(self, token: str) -> dict[str, Any]:
        now = self._current_time()
        record = self._tokens_by_hash.get(self._hash(token)) if isinstance(token, str) else None
        if record is None:
            return self._inactive("TOKEN_UNKNOWN", now)
        if record.revoked_at is not None:
            return self._deny(record, "TOKEN_REVOKED", now)
        if record.expires_at <= now:
            return self._deny(record, "TOKEN_EXPIRED", now)
        if record.consumed_at is not None:
            return self._deny(record, "TOKEN_REPLAYED", now)
        record.consumed_at = now
        self._record("TOKEN_INTROSPECTED", record.claims, token_id=record.token_id)
        return {
            "schema_version": _SCHEMA_VERSION, "active": True, "evaluated_at": self._format_time(now),
            "token_id": record.token_id, "subject_id": record.claims["subject_id"],
            "actor_id": record.claims["actor_id"], "mission_id": record.claims["mission_id"],
            "organization_id": record.claims["organization_id"], "workspace_id": record.claims["workspace_id"],
            "audience": record.claims["target_audience"], "operation": record.claims["operation"],
            "binding_id": record.claims["binding_id"], "binding_version": record.claims["binding_version"],
            "expires_at": record.claims["expires_at"], "authorization_assertion_id": record.claims["assertion_id"],
        }

    def revoke(self, *, token_id: str | None = None, assertion_id: str | None = None, binding_id: str | None = None) -> int:
        references = [value for value in (token_id, assertion_id, binding_id) if value]
        if len(references) != 1:
            raise STSError("exactly one revocation reference is required")
        records = self._tokens_by_id.values() if token_id is None else [self._tokens_by_id.get(token_id)]
        revoked = 0
        for record in records:
            if record is None or (assertion_id and record.claims["assertion_id"] != assertion_id) or (binding_id and record.claims["binding_id"] != binding_id):
                continue
            if record.revoked_at is None:
                record.revoked_at = self._current_time()
                revoked += 1
                self._record("TOKEN_REVOKED", record.claims, token_id=record.token_id)
        return revoked

    def _validate_claims(self, claims: Mapping[str, Any]) -> dict[str, str]:
        required = {
            "schema_version", "assertion_id", "issuer", "audience", "subject_id", "actor_id", "mission_id",
            "organization_id", "workspace_id", "target_product", "target_audience", "operation", "binding_id",
            "binding_version", "issued_at", "expires_at", "correlation_id",
        }
        if set(claims) != required or not all(isinstance(claims[key], str) and claims[key] for key in required):
            raise STSError("invalid assertion claims")
        values = dict(claims)
        if (
            values["schema_version"] != _SCHEMA_VERSION or values["issuer"] != "aquila"
            or values["audience"] != _STS_AUDIENCE or values["actor_id"] != "aquila"
            or values["target_product"] != "TABULA" or values["target_audience"] != _TABULA_AUDIENCE
            or values["operation"] not in _OPERATIONS or not _VERSION.fullmatch(values["binding_version"])
            or len(values["subject_id"]) > 512
        ):
            raise STSError("invalid assertion claims")
        for key in ("assertion_id", "mission_id", "organization_id", "workspace_id", "binding_id", "correlation_id"):
            try:
                UUID(values[key])
            except ValueError as exc:
                raise STSError("invalid assertion claims") from exc
        issued_at, expires_at, now = self._parse_time(values["issued_at"]), self._parse_time(values["expires_at"]), self._current_time()
        if issued_at > now + _CLOCK_SKEW or expires_at <= now or expires_at <= issued_at or expires_at - issued_at > _MAX_TOKEN_LIFETIME:
            raise STSError("invalid assertion lifetime")
        return values

    def _deny(self, record: _TokenRecord, code: str, now: datetime) -> dict[str, Any]:
        self._record("TOKEN_INTROSPECTED", record.claims, token_id=record.token_id, outcome="DENIED")
        return self._inactive(code, now)

    def _inactive(self, denial_code: str, now: datetime) -> dict[str, Any]:
        return {"schema_version": _SCHEMA_VERSION, "active": False, "evaluated_at": self._format_time(now), "denial_code": denial_code}

    def _record(self, event_type: str, claims: Mapping[str, str] | None = None, *, token_id: str | None = None, outcome: str = "ALLOWED") -> None:
        values = claims or {}
        self.audit_events.append(STSAuditEvent(
            event_type=event_type, occurred_at=self._format_time(self._current_time()), token_id=token_id,
            authorization_assertion_id=values.get("assertion_id"), correlation_id=values.get("correlation_id"),
            mission_id=values.get("mission_id"), binding_id=values.get("binding_id"), operation=values.get("operation"), outcome=outcome,
        ))

    @staticmethod
    def _hash(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def _current_time(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise ValueError("STS clock must return a timezone-aware datetime")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _parse_time(value: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise STSError("invalid assertion time") from exc
        if parsed.tzinfo is None:
            raise STSError("invalid assertion time")
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _format_time(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
