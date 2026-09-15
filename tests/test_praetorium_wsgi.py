import io
import json
import unittest
from urllib.parse import urlencode

from aquila_api.auth import AuthentikConfig, AuthentikPrincipalMapper, BearerAuthenticator
from aquila_api.service import AquilaService
from legion_kernel import LegionKernel
from praetorium import PraetoriumWSGIApp


class Verifier:
    def verify(self, token):
        if token != "human":
            raise ValueError("invalid")
        return {"iss": "https://auth.example/", "aud": "aquila", "sub": "operator", "groups": ["legion/mission-operators"]}


class PraetoriumWSGITests(unittest.TestCase):
    def setUp(self):
        mapper = AuthentikPrincipalMapper(AuthentikConfig(issuer="https://auth.example/", audience="aquila"))
        self.service = AquilaService(LegionKernel())
        self.app = PraetoriumWSGIApp(self.service, BearerAuthenticator(Verifier(), mapper), tabula_console_url="https://tabula.example/console")

    def request(self, method, path, form=None, authorization="Bearer human"):
        raw = urlencode(form or {}).encode()
        captured = {}
        def start(status, headers): captured.update(status=int(status[:3]), headers=dict(headers))
        body = b"".join(self.app({"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw), "HTTP_AUTHORIZATION": authorization}, start)).decode()
        return captured, body

    def mission(self):
        actor = self.app.authenticator.authenticate("Bearer human")
        return self.service.create_mission(actor=actor, body={"organization_id": "11111111-1111-4111-8111-111111111111", "workspace_id": "22222222-2222-4222-8222-222222222222", "title": "Operator view", "objective": "Render an authorized Mission.", "initial_roe_level": "REVIEW"}).body

    def test_renders_authorized_list_and_detail_with_tabula_deep_link(self):
        mission = self.mission()
        response, body = self.request("GET", "/praetorium/missions")
        self.assertEqual(response["status"], 200)
        self.assertIn("Operator view", body)
        response, body = self.request("GET", f"/praetorium/missions/{mission['id']}")
        self.assertEqual(response["status"], 200)
        self.assertIn("https://tabula.example/console", body)
        self.assertNotIn("pts_", body)

    def test_command_form_delegates_to_aquila(self):
        mission = self.mission()
        response, body = self.request("POST", f"/praetorium/missions/{mission['id']}/commands", {"expected_version": "1", "idempotency_key": "start-ui", "command_type": "START", "payload_json": json.dumps({})})
        self.assertEqual(response["status"], 200)
        self.assertIn("ACCEPTED", body)
        self.assertEqual(self.service.kernel.get_mission(mission["id"]).status.value, "ACTIVE")

    def test_requires_authenticated_human(self):
        response, body = self.request("GET", "/praetorium/missions", authorization=None)
        self.assertEqual(response["status"], 401)
        self.assertIn("UNAUTHENTICATED", body)
