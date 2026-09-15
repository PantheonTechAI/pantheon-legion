"""First Phase 4 operator journey through the Praetorium HTTP surface."""

import io
import json
import unittest
from urllib.parse import urlencode

from aquila_api.auth import AuthentikConfig, AuthentikPrincipalMapper, BearerAuthenticator
from aquila_api.service import AquilaService
from legion_kernel import LegionKernel
from praetorium import PraetoriumWSGIApp


class _Verifier:
    def verify(self, token):
        if token != "operator":
            raise ValueError("invalid")
        return {"iss": "https://auth.example/", "aud": "aquila", "sub": "owner", "groups": ["legion/mission-owners", "legion/mission-approvers"]}


class PraetoriumUserAcceptanceTests(unittest.TestCase):
    def setUp(self):
        mapper = AuthentikPrincipalMapper(AuthentikConfig(issuer="https://auth.example/", audience="aquila"))
        self.service = AquilaService(LegionKernel())
        self.app = PraetoriumWSGIApp(self.service, BearerAuthenticator(_Verifier(), mapper), tabula_console_url="https://tabula.example/console")
        actor = self.app.authenticator.authenticate("Bearer operator")
        self.mission = self.service.create_mission(actor=actor, body={"organization_id": "11111111-1111-4111-8111-111111111111", "workspace_id": "22222222-2222-4222-8222-222222222222", "title": "Approval journey", "objective": "Prove the bounded operator path.", "initial_roe_level": "REVIEW"}).body

    def request(self, method, path, form=None):
        raw, captured = urlencode(form or {}).encode(), {}
        def start(status, headers): captured.update(status=int(status[:3]))
        body = b"".join(self.app({"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw), "HTTP_AUTHORIZATION": "Bearer operator"}, start)).decode()
        return captured["status"], body

    def test_operator_can_inspect_submit_approve_and_follow_tabula_link(self):
        mission_id = self.mission["id"]
        status, body = self.request("GET", f"/praetorium/missions/{mission_id}")
        self.assertEqual(status, 200)
        self.assertIn("https://tabula.example/console", body)
        status, _ = self.request("POST", f"/praetorium/missions/{mission_id}/commands", {"expected_version": "1", "idempotency_key": "start", "command_type": "START", "payload_json": "{}"})
        self.assertEqual(status, 200)
        payload = {"action_id": "33333333-3333-4333-8333-333333333333", "capability": "test.mutation", "arguments": {"target": "resource"}, "target": "resource", "side_effect_class": "MUTATION"}
        status, body = self.request("POST", f"/praetorium/missions/{mission_id}/commands", {"expected_version": "2", "idempotency_key": "request", "command_type": "REQUEST_ACTION", "payload_json": json.dumps(payload)})
        self.assertEqual(status, 200)
        self.assertIn("PENDING", body)
        approval = next(value for value in self.service.kernel.approvals.values() if value.mission_id == mission_id)
        status, body = self.request("POST", f"/praetorium/missions/{mission_id}/approvals/{approval.id}", {"expected_mission_version": "3", "decision": "APPROVE", "reason": "Reviewed bounded action."})
        self.assertEqual(status, 200)
        self.assertIn("APPROVED", body)
        self.assertNotIn("pts_", body)
