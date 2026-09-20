"""Short-lived HTTP host for the deterministic STS conformance fixture."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
import json
from threading import Thread
from typing import Any
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pantheon_sts import Ed25519AssertionVerifier, InMemorySecurityTokenService, sign_assertion
from pantheon_sts.wsgi import STSWSGIApp, StaticServiceAuthenticator


class FixtureSTSServer(AbstractContextManager):
    """Run a fixture-only STS server for one disposable conformance session."""

    def __init__(self, *, host: str = "127.0.0.1", port: int = 0) -> None:
        private_key = Ed25519PrivateKey.generate()
        verifier = Ed25519AssertionVerifier({"aquila-fixture": private_key.public_key()})
        self._private_key = private_key
        self._clock = _FixtureClock()
        self._service = InMemorySecurityTokenService(verifier, now=self._clock.now)
        self._host = host
        self._requested_port = port
        self._server = None
        self._thread: Thread | None = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("fixture STS is not running")
        connect_host = "127.0.0.1" if self._host == "0.0.0.0" else self._host
        return f"http://{connect_host}:{self._server.server_port}"

    @property
    def introspection_url(self) -> str:
        return f"{self.base_url}/v1/introspect"

    @property
    def current_time(self) -> datetime:
        """Expose the deterministic fixture clock for assertion construction."""
        return self._clock.now()

    @property
    def docker_introspection_url(self) -> str:
        """Return the host-gateway URL only when explicitly bound for Docker."""
        if self._host != "0.0.0.0" or self._server is None:
            raise RuntimeError("bind the fixture STS to 0.0.0.0 before exposing it to Docker")
        return f"http://host.docker.internal:{self._server.server_port}/v1/introspect"

    def __enter__(self):
        app = STSWSGIApp(
            self._service,
            StaticServiceAuthenticator({"aquila": {"issue", "revoke"}, "tabula": {"introspect"}}),
        )
        self._server = make_server(self._host, self._requested_port, app, handler_class=_QuietHandler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join()
        self._server = None
        self._thread = None

    def issue_token(self, claims: dict[str, Any]) -> str:
        """Sign an assertion locally and request exactly one opaque STS token."""
        assertion = sign_assertion(claims, self._private_key, key_id="aquila-fixture")
        response = _post_json(
            f"{self.base_url}/v1/delegated-tokens", {"assertion": assertion}, "aquila"
        )
        token = response.get("token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("fixture STS did not issue a token")
        return token

    def revoke_binding(self, binding_id: str) -> int:
        """Revoke fixture tokens by binding through the same HTTP boundary as Aquila."""
        response = _post_json(
            f"{self.base_url}/v1/revocations", {"binding_id": binding_id}, "aquila"
        )
        revoked = response.get("revoked")
        if not isinstance(revoked, int) or isinstance(revoked, bool):
            raise RuntimeError("fixture STS returned an invalid revocation response")
        return revoked

    def advance(self, duration: timedelta) -> None:
        """Move the fixture clock forward without sleeping in conformance tests."""
        self._clock.advance(duration)


class _FixtureClock:
    def __init__(self) -> None:
        self._value = datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._value

    def advance(self, duration: timedelta) -> None:
        if duration <= timedelta(0):
            raise ValueError("fixture clock can only move forward")
        self._value += duration


def _post_json(url: str, payload: dict[str, Any], identity: str) -> dict[str, Any]:
    request = Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "X-Pantheon-Service": identity},
    )
    with urlopen(request, timeout=3.0) as response:
        decoded = json.loads(response.read().decode("utf-8"))
    if not isinstance(decoded, dict):
        raise RuntimeError("fixture STS returned a non-object response")
    return decoded


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return
