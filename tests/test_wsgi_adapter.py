import io
import json
import unittest

from aquila_api.auth import AuthentikConfig, AuthentikPrincipalMapper, BearerAuthenticator
from aquila_api.service import AquilaService
from aquila_api.wsgi import AquilaWSGIApp
from legion_kernel import LegionKernel


class FakeVerifier:
    def verify(self, token):
        if token != "valid-token":
            raise ValueError("invalid")
        return {
            "iss": "https://authentik.example/",
            "aud": "aquila",
            "sub": "owner",
            "groups": ["legion/mission-owners", "legion/mission-operators"],
        }


class WsgiAdapterTests(unittest.TestCase):
    def setUp(self):
        mapper = AuthentikPrincipalMapper(
            AuthentikConfig(issuer="https://authentik.example/", audience="aquila")
        )
        authenticator = BearerAuthenticator(FakeVerifier(), mapper)
        self.app = AquilaWSGIApp(AquilaService(LegionKernel()), authenticator)

    def request(self, method, path, body=None, authorization="Bearer valid-token"):
        encoded = json.dumps(body).encode() if body is not None else b""
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path.split("?", 1)[0],
            "QUERY_STRING": path.split("?", 1)[1] if "?" in path else "",
            "CONTENT_LENGTH": str(len(encoded)),
            "wsgi.input": io.BytesIO(encoded),
            "HTTP_AUTHORIZATION": authorization,
        }
        captured = {}

        def start_response(status, headers):
            captured["status"] = int(status.split(" ", 1)[0])
            captured["headers"] = dict(headers)

        payload = b"".join(self.app(environ, start_response))
        return captured["status"], captured["headers"], json.loads(payload)

    def create_body(self):
        return {
            "organization_id": "11111111-1111-4111-8111-111111111111",
            "workspace_id": "22222222-2222-4222-8222-222222222222",
            "title": "WSGI Mission",
            "objective": "Exercise the HTTP edge.",
            "initial_roe_level": "REVIEW",
        }

    def test_create_read_and_command_routes(self):
        status, headers, created = self.request("POST", "/missions", self.create_body())
        self.assertEqual(status, 201)
        self.assertIn("Location", headers)
        mission_id = created["id"]
        status, _, read = self.request("GET", f"/missions/{mission_id}")
        self.assertEqual(status, 200)
        self.assertEqual(read["version"], 1)
        status, _, command = self.request(
            "POST",
            f"/missions/{mission_id}/commands",
            {"expected_version": 1, "idempotency_key": "start", "command_type": "START", "payload": {}},
        )
        self.assertEqual(status, 200)
        self.assertEqual(command["status"], "ACCEPTED")

    def test_authentication_and_error_routes(self):
        status, _, body = self.request("GET", "/missions/unknown", authorization=None)
        self.assertEqual(status, 401)
        self.assertEqual(body["code"], "UNAUTHENTICATED")
        status, _, body = self.request("GET", "/unknown")
        self.assertEqual(status, 404)
        self.assertEqual(body["code"], "NOT_FOUND")

    def test_timeline_query_and_stale_command(self):
        _, _, created = self.request("POST", "/missions", self.create_body())
        mission_id = created["id"]
        self.request(
            "POST", f"/missions/{mission_id}/commands",
            {"expected_version": 1, "idempotency_key": "start", "command_type": "START", "payload": {}},
        )
        status, _, stale = self.request(
            "POST", f"/missions/{mission_id}/commands",
            {"expected_version": 1, "idempotency_key": "stale", "command_type": "PAUSE", "payload": {}},
        )
        self.assertEqual(status, 409)
        self.assertEqual(stale["code"], "VERSION_CONFLICT")
        status, _, timeline = self.request("GET", f"/missions/{mission_id}/timeline?limit=1")
        self.assertEqual(status, 200)
        self.assertTrue(timeline["has_more"])
        self.assertEqual(len(timeline["events"]), 1)

    def test_invalid_json_is_rejected(self):
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/missions",
            "QUERY_STRING": "",
            "CONTENT_LENGTH": "7",
            "wsgi.input": io.BytesIO(b"not-json"),
            "HTTP_AUTHORIZATION": "Bearer valid-token",
        }
        captured = {}

        def start_response(status, headers):
            captured["status"] = int(status.split(" ", 1)[0])

        body = json.loads(b"".join(self.app(environ, start_response)))
        self.assertEqual(captured["status"], 400)
        self.assertEqual(body["code"], "INVALID_REQUEST")
