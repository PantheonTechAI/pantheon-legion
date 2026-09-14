import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pantheon_sts import (
    Ed25519AssertionVerifier,
    InMemorySecurityTokenService,
    STSWSGIApp,
    StaticServiceAuthenticator,
    sign_assertion,
)
from pantheon_sts.service import STSError


class SecurityTokenServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 14, tzinfo=timezone.utc)
        self.private_key = Ed25519PrivateKey.generate()
        self.service = InMemorySecurityTokenService(
            Ed25519AssertionVerifier({"aquila-test": self.private_key.public_key()}),
            now=lambda: self.now,
        )

    def _claims(self, **overrides):
        values = {
            "schema_version": "1.0", "assertion_id": str(uuid4()), "issuer": "aquila",
            "audience": "pantheon-sts", "subject_id": "scout-1", "actor_id": "aquila",
            "mission_id": str(uuid4()), "organization_id": str(uuid4()), "workspace_id": str(uuid4()),
            "target_product": "TABULA", "target_audience": "pantheon-tabula-mcp",
            "operation": "TABULA_CORPUS_READ", "binding_id": str(uuid4()), "binding_version": "1.0.0",
            "issued_at": self.now.isoformat().replace("+00:00", "Z"),
            "expires_at": (self.now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "correlation_id": str(uuid4()),
        }
        values.update(overrides)
        return values

    def _issue(self, **overrides):
        claims = self._claims(**overrides)
        return self.service.issue(sign_assertion(claims, self.private_key, key_id="aquila-test")), claims

    def test_signed_assertion_issues_one_time_opaque_token_and_exact_introspection(self):
        issued, claims = self._issue()
        self.assertTrue(issued.token.startswith("pts_"))
        status = self.service.introspect(issued.token)
        self.assertTrue(status["active"])
        self.assertEqual(status["token_id"], issued.token_id)
        self.assertEqual(status["organization_id"], claims["organization_id"])
        self.assertEqual(status["workspace_id"], claims["workspace_id"])
        self.assertEqual(status["authorization_assertion_id"], claims["assertion_id"])
        replay = self.service.introspect(issued.token)
        self.assertFalse(replay["active"])
        self.assertEqual(replay["denial_code"], "TOKEN_REPLAYED")
        self.assertNotIn(issued.token, repr(self.service.audit_events))

    def test_assertion_signature_replay_and_lifetime_fail_closed(self):
        claims = self._claims()
        signed = sign_assertion(claims, self.private_key, key_id="aquila-test")
        self.service.issue(signed)
        with self.assertRaises(STSError):
            self.service.issue(signed)
        other_key = Ed25519PrivateKey.generate()
        with self.assertRaises(STSError):
            self.service.issue(sign_assertion(self._claims(), other_key, key_id="aquila-test"))
        with self.assertRaises(STSError):
            self._issue(expires_at=(self.now + timedelta(minutes=6)).isoformat().replace("+00:00", "Z"))

    def test_expiry_and_revocation_deny_before_a_token_can_be_used(self):
        issued, _ = self._issue()
        self.assertEqual(self.service.revoke(token_id=issued.token_id), 1)
        self.assertEqual(self.service.introspect(issued.token)["denial_code"], "TOKEN_REVOKED")
        issued, _ = self._issue()
        self.now += timedelta(minutes=6)
        self.assertEqual(self.service.introspect(issued.token)["denial_code"], "TOKEN_EXPIRED")

    def test_wsgi_requires_distinct_fixture_service_identities(self):
        app = STSWSGIApp(
            self.service,
            StaticServiceAuthenticator({"aquila": {"issue", "revoke"}, "tabula": {"introspect"}}),
        )
        claims = self._claims()
        signed = sign_assertion(claims, self.private_key, key_id="aquila-test")
        status, body = self._call(app, "/v1/delegated-tokens", {"assertion": signed}, "aquila")
        self.assertEqual(status, 201)
        denied_status, _ = self._call(app, "/v1/introspect", {"token": body["token"]}, None)
        self.assertEqual(denied_status, 401)
        status, introspection = self._call(app, "/v1/introspect", {"token": body["token"]}, "tabula")
        self.assertEqual(status, 200)
        self.assertTrue(introspection["active"])

    @staticmethod
    def _call(app, path, body, identity):
        encoded = json.dumps(body).encode()
        captured = {}

        def start_response(status, _headers):
            captured["status"] = int(status.split()[0])

        environ = {"REQUEST_METHOD": "POST", "PATH_INFO": path, "CONTENT_LENGTH": str(len(encoded)), "wsgi.input": io.BytesIO(encoded)}
        if identity:
            environ["HTTP_X_PANTHEON_SERVICE"] = identity
        response = json.loads(b"".join(app(environ, start_response)).decode())
        return captured["status"], response


if __name__ == "__main__":
    unittest.main()
