import io
import json
import unittest
from urllib.parse import urlencode

from aquila_api.auth import AuthentikConfig, AuthentikPrincipalMapper, BearerAuthenticator
from aquila_api.service import AquilaService
from legion_kernel import LegionKernel
from legion_runtime import (
    MissionAgentView,
    MissionEvidenceView,
    MissionOrganizationSnapshot,
    MissionWorkView,
)
from praetorium import PraetoriumWSGIApp

ORGANIZATION_ID = "11111111-1111-4111-8111-111111111111"
WORKSPACE_ID = "22222222-2222-4222-8222-222222222222"


class Verifier:
    def verify(self, token):
        if token not in {"human", "denied"}:
            raise ValueError("invalid")
        return {
            "iss": "https://auth.example/",
            "aud": "aquila",
            "sub": "operator",
            "groups": ["legion/mission-operators"] if token == "human" else [],
        }


class OrganizationReadModel:
    def __init__(
        self,
        *,
        error=None,
        canonical_uri='https://example.test/"citation',
    ):
        self.calls = []
        self.error = error
        self.canonical_uri = canonical_uri

    def snapshot(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return MissionOrganizationSnapshot(
            mission_id=kwargs["mission_id"],
            agents=(
                MissionAgentView(
                    agent_id="33333333-3333-4333-8333-333333333333",
                    display_name="Scout <one>",
                    role="SCOUT",
                    assignment_status="ASSIGNED",
                ),
            ),
            work=(
                MissionWorkView(
                    work_item_id="44444444-4444-4444-8444-444444444444",
                    work_kind="GROUNDED_CORPUS_ANALYSIS",
                    objective="Inspect <unsafe> evidence",
                    status="COMPLETED",
                    created_at="2026-09-18T00:00:00Z",
                    updated_at="2026-09-18T00:01:00Z",
                    result_summary="Bounded <result>",
                    result_digest="digest-one",
                    evidence=(
                        MissionEvidenceView(
                            evidence_reference_id=(
                                "55555555-5555-4555-8555-555555555555"
                            ),
                            external_record_id="record-<one>",
                            external_revision="rev-1",
                            canonical_uri=self.canonical_uri,
                            retrieved_at="2026-09-18T00:01:00Z",
                        ),
                    ),
                ),
            ),
        )


class PraetoriumWSGITests(unittest.TestCase):
    def setUp(self):
        mapper = AuthentikPrincipalMapper(AuthentikConfig(issuer="https://auth.example/", audience="aquila"))
        self.service = AquilaService(LegionKernel())
        self.app = PraetoriumWSGIApp(
            self.service,
            BearerAuthenticator(Verifier(), mapper),
            tabula_console_url="https://tabula.example/console",
            organization_id=ORGANIZATION_ID,
            workspace_id=WORKSPACE_ID,
        )

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

    def test_root_redirects_to_missions(self):
        response, body = self.request("GET", "/")
        self.assertEqual(response["status"], 303)
        self.assertEqual(response["headers"]["Location"], "/praetorium/missions")
        self.assertEqual(body, "")

    def test_create_mission_uses_server_scope_not_browser_scope(self):
        response, body = self.request("GET", "/praetorium/missions/new")
        self.assertNotIn('name="organization_id"', body)
        self.assertNotIn('name="workspace_id"', body)
        response, body = self.request("POST", "/praetorium/missions", {"organization_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "workspace_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "title": "Server scoped Mission", "objective": "Prove browser scope is ignored.", "initial_roe_level": "REVIEW"})
        self.assertEqual(response["status"], 303)
        self.assertEqual(body, "")
        mission = next(iter(self.service.kernel.missions.values()))
        self.assertEqual(mission.organization_id, ORGANIZATION_ID)
        self.assertEqual(mission.workspace_id, WORKSPACE_ID)
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

    def test_authorized_detail_renders_escaped_runtime_projection(self):
        mission = self.mission()
        read_model = OrganizationReadModel()
        self.app.organization_read_model = read_model
        response, body = self.request(
            "GET", f"/praetorium/missions/{mission['id']}"
        )
        self.assertEqual(response["status"], 200)
        self.assertIn("Persistent organization", body)
        self.assertIn("Scout &lt;one&gt;", body)
        self.assertIn("Bounded &lt;result&gt;", body)
        self.assertIn("record-&lt;one&gt;", body)
        self.assertIn("&quot;citation", body)
        self.assertNotIn("<unsafe>", body)
        self.assertEqual(read_model.calls[0]["organization_id"], ORGANIZATION_ID)

    def test_runtime_projection_failure_isolated_from_mission_detail(self):
        mission = self.mission()
        self.app.organization_read_model = OrganizationReadModel(
            error=TimeoutError("database details must not render")
        )
        response, body = self.request(
            "GET", f"/praetorium/missions/{mission['id']}"
        )
        self.assertEqual(response["status"], 200)
        self.assertIn("Operator view", body)
        self.assertIn("Organization status unavailable.", body)
        self.assertNotIn("database details", body)

    def test_non_web_citation_uri_is_visible_but_never_clickable(self):
        mission = self.mission()
        self.app.organization_read_model = OrganizationReadModel(
            canonical_uri="javascript:alert(document.domain)"
        )

        response, body = self.request(
            "GET", f"/praetorium/missions/{mission['id']}"
        )

        self.assertEqual(response["status"], 200)
        self.assertIn("javascript:alert(document.domain)", body)
        self.assertIn("(non-web URI)", body)
        self.assertNotIn('href="javascript:', body.lower())

    def test_mission_denial_prevents_runtime_projection_call(self):
        mission = self.mission()
        read_model = OrganizationReadModel()
        self.app.organization_read_model = read_model
        response, _ = self.request(
            "GET",
            f"/praetorium/missions/{mission['id']}",
            authorization="Bearer denied",
        )
        self.assertEqual(response["status"], 403)
        self.assertEqual(read_model.calls, [])
