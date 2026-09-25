"""Human launch remains one explicit, authenticated Praetorium action."""

import io
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from aquila_api import PersistentAquilaService
from aquila_api.service import ApiResponse
from legion_kernel import Principal, PrincipalType
from praetorium import PraetoriumWSGIApp


class OwnerAuthenticator:
    def authenticate_request(self, environ):
        return Principal(PrincipalType.HUMAN, "owner", frozenset({"MISSION_OWNER"}))


class InvestigationPraetoriumTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = PersistentAquilaService(
            str(Path(self.temp.name) / "aquila.sqlite3"),
            investigation_subjects=("centurion", "scout"),
        )
        self.app = PraetoriumWSGIApp(
            self.service, OwnerAuthenticator(), tabula_console_url="https://tabula.example/",
            organization_id="11111111-1111-4111-8111-111111111111",
            workspace_id="22222222-2222-4222-8222-222222222222",
        )
        self.owner = OwnerAuthenticator().authenticate_request({})
        self.mission_id = self.service.create_mission(actor=self.owner, body={
            "organization_id": self.app.organization_id,
            "workspace_id": self.app.workspace_id,
            "title": "Read-only investigation",
            "objective": "Which accepted ADRs govern Scout evidence?",
        }).body["id"]

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def request(self, method, path, *, origin="https://legion.example"):
        captured = {}
        def start(status, headers):
            captured.update(status=int(status[:3]), headers=dict(headers))
        body = b"".join(self.app({
            "REQUEST_METHOD": method, "PATH_INFO": path,
            "HTTP_HOST": "legion.example", "HTTP_ORIGIN": origin,
            "CONTENT_LENGTH": "0", "wsgi.input": io.BytesIO(b""),
        }, start)).decode()
        return captured, body

    def test_start_action_is_idempotent_and_visible(self):
        path = f"/praetorium/missions/{self.mission_id}"
        initial, html = self.request("GET", path)
        self.assertEqual(initial["status"], 200)
        self.assertIn("Start investigation", html)
        denied, _ = self.request("POST", path + "/investigation", origin="https://other.example")
        self.assertEqual(denied["status"], 403)
        self.assertEqual(self.service.store.get_mission(self.mission_id).version, 1)
        started, _ = self.request("POST", path + "/investigation")
        self.assertEqual(started["status"], 303)
        again, _ = self.request("POST", path + "/investigation")
        self.assertEqual(again["status"], 303)
        self.assertEqual(self.service.store.get_mission(self.mission_id).version, 3)
        self.assertEqual(len(self.service.delegations), 2)
        status, html = self.request("GET", path)
        self.assertEqual(status["status"], 200)
        self.assertIn("Requested; delivery PENDING", html)
        self.assertNotIn("centurion_grant_id", html)


    def test_rejected_launch_can_be_retried_from_same_ui(self):
        path = f"/praetorium/missions/{self.mission_id}/investigation"
        submit = self.service.submit_command
        keys = []
        def reject_once(**kwargs):
            if kwargs["body"]["command_type"] == "REQUEST_INVESTIGATION":
                keys.append(kwargs["body"]["idempotency_key"])
                if len(keys) == 1:
                    return ApiResponse(409, {"code": "VERSION_CONFLICT"}, {})
            return submit(**kwargs)
        with mock.patch.object(self.service, "submit_command", side_effect=reject_once):
            first, _ = self.request("POST", path)
            second, _ = self.request("POST", path)
        self.assertEqual(first["status"], 200)
        self.assertEqual(second["status"], 303)
        self.assertEqual(len(keys), 2)
        self.assertNotEqual(keys[0], keys[1])
        self.assertEqual(self.service.outbox.get_by_mission(self.mission_id).status, "PENDING")


if __name__ == "__main__":
    unittest.main()
