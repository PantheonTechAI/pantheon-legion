"""Minimal WSGI transport for the deterministic STS conformance fixture."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import Mapping

from .service import InMemorySecurityTokenService, STSError


@dataclass(frozen=True)
class StaticServiceAuthenticator:
    """Fixture-only identity check; a production service must use mTLS."""

    identities: Mapping[str, set[str]]

    def permits(self, identity: str | None, operation: str) -> bool:
        return bool(identity and operation in self.identities.get(identity, set()))


class STSWSGIApp:
    """Expose issue, introspection, and revocation over a small JSON API."""

    def __init__(self, service: InMemorySecurityTokenService, authenticator: StaticServiceAuthenticator) -> None:
        self.service = service
        self.authenticator = authenticator

    def __call__(self, environ, start_response):
        method, path = environ.get("REQUEST_METHOD", "GET").upper(), environ.get("PATH_INFO", "")
        routes = {
            ("POST", "/v1/delegated-tokens"): ("issue", self._issue),
            ("POST", "/v1/introspect"): ("introspect", self._introspect),
            ("POST", "/v1/revocations"): ("revoke", self._revoke),
        }
        route = routes.get((method, path))
        if route is None:
            return self._send(start_response, 404, {"code": "NOT_FOUND"})
        operation, handler = route
        if not self.authenticator.permits(environ.get("HTTP_X_PANTHEON_SERVICE"), operation):
            return self._send(start_response, 401, {"code": "UNAUTHENTICATED"})
        try:
            body = self._read_json(environ)
            status, response = handler(body)
        except STSError:
            return self._send(start_response, 422, {"code": "INVALID_REQUEST"})
        except ValueError:
            return self._send(start_response, 400, {"code": "INVALID_REQUEST"})
        return self._send(start_response, status, response)

    def _issue(self, body: dict) -> tuple[int, dict]:
        if set(body) != {"assertion"} or not isinstance(body["assertion"], str):
            raise ValueError("invalid issue request")
        return 201, self.service.issue(body["assertion"]).response()

    def _introspect(self, body: dict) -> tuple[int, dict]:
        if set(body) != {"token"} or not isinstance(body["token"], str):
            raise ValueError("invalid introspection request")
        return 200, self.service.introspect(body["token"])

    def _revoke(self, body: dict) -> tuple[int, dict]:
        allowed = {"token_id", "assertion_id", "binding_id"}
        if not body or set(body) - allowed or any(not isinstance(value, str) for value in body.values()):
            raise ValueError("invalid revocation request")
        return 200, {"revoked": self.service.revoke(**body)}

    @staticmethod
    def _read_json(environ) -> dict:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        raw = environ.get("wsgi.input", io.BytesIO()).read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid JSON") from exc
        if not isinstance(body, dict):
            raise ValueError("request body must be an object")
        return body

    @staticmethod
    def _send(start_response, status: int, body: dict):
        reasons = {200: "OK", 201: "Created", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found", 422: "Unprocessable Entity"}
        encoded = json.dumps(body, sort_keys=True).encode("utf-8")
        start_response(f"{status} {reasons[status]}", [("Content-Type", "application/json"), ("Content-Length", str(len(encoded)))])
        return [encoded]
