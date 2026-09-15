"""A small authenticated Praetorium operations surface.

The browser presents only a human bearer token.  All Mission reads, commands,
and Approval decisions are delegated to Aquila; this module owns no Mission
state and never receives a workload grant or Tabula service credential.
"""

from __future__ import annotations

from html import escape
import io
import json
from urllib.parse import parse_qs, quote

from aquila_api.auth import AuthenticationError, BearerAuthenticator
from aquila_api.service import AquilaService


class PraetoriumWSGIApp:
    def __init__(self, service: AquilaService, authenticator: BearerAuthenticator, *, tabula_console_url: str) -> None:
        self.service, self.authenticator = service, authenticator
        self.tabula_console_url = tabula_console_url.rstrip("/")

    def __call__(self, environ, start_response):
        try:
            authenticate_request = getattr(self.authenticator, "authenticate_request", None)
            actor = authenticate_request(environ) if authenticate_request else self.authenticator.authenticate(environ.get("HTTP_AUTHORIZATION"))
        except AuthenticationError as error:
            return self._send(start_response, 401, self._page("Sign in required", f"<p>{escape(str(error))}</p>"))
        method, path = environ.get("REQUEST_METHOD", "GET").upper(), environ.get("PATH_INFO", "")
        if path in {"/praetorium", "/praetorium/"} and method == "GET":
            return self._redirect(start_response, "/praetorium/missions")
        if path == "/praetorium/missions" and method == "GET":
            return self._missions(start_response, actor)
        if path == "/praetorium/missions/new" and method == "GET":
            return self._new_mission(start_response)
        if path == "/praetorium/missions" and method == "POST":
            return self._create_mission(start_response, actor, environ)
        parts = [part for part in path.split("/") if part]
        if len(parts) == 3 and parts[:2] == ["praetorium", "missions"] and method == "GET":
            return self._mission(start_response, actor, parts[2])
        if len(parts) == 4 and parts[:2] == ["praetorium", "missions"] and parts[3] == "commands" and method == "POST":
            return self._command(start_response, actor, parts[2], environ)
        if len(parts) == 5 and parts[:2] == ["praetorium", "missions"] and parts[3] == "approvals" and method == "POST":
            return self._approval(start_response, actor, parts[2], parts[4], environ)
        return self._send(start_response, 404, self._page("Not found", "<p>Not found.</p>"))

    def _missions(self, start_response, actor):
        response = self.service.list_missions(actor=actor)
        if response.status_code != 200:
            return self._error(start_response, response)
        rows = "".join(
            f'<li><a href="/praetorium/missions/{quote(item["id"])}">{escape(item["title"])}</a> '
            f'— {escape(item["status"])} (v{item["version"]})</li>'
            for item in response.body["missions"]
        ) or "<li>No visible Missions.</li>"
        return self._send(start_response, 200, self._page("Praetorium Missions", f'<h1>Praetorium</h1><p><a href="/praetorium/missions/new">Create Mission</a></p><ul>{rows}</ul>'))

    def _new_mission(self, start_response):
        form = '''<h1>Create Mission</h1><form method="post" action="/praetorium/missions">
<input name="organization_id" required placeholder="Organization UUID"><input name="workspace_id" required placeholder="Workspace UUID">
<input name="title" required maxlength="200" placeholder="Title"><textarea name="objective" required maxlength="10000" placeholder="Objective"></textarea>
<select name="initial_roe_level"><option>OBSERVE</option><option>RECOMMEND</option><option>REVIEW</option></select><button>Create Mission</button></form>'''
        return self._send(start_response, 200, self._page("Create Mission", form))

    def _create_mission(self, start_response, actor, environ):
        form = self._form(environ)
        body = {key: form.get(key, "") for key in ("organization_id", "workspace_id", "title", "objective", "initial_roe_level")}
        response = self.service.create_mission(actor=actor, body=body)
        if response.status_code != 201:
            return self._error(start_response, response)
        return self._redirect(start_response, f'/praetorium/missions/{quote(response.body["id"])}')

    def _mission(self, start_response, actor, mission_id: str, notice: str = ""):
        mission, timeline, approvals = (self.service.get_mission(actor=actor, mission_id=mission_id),
                                        self.service.get_timeline(actor=actor, mission_id=mission_id),
                                        self.service.list_approvals(actor=actor, mission_id=mission_id))
        if mission.status_code != 200:
            return self._error(start_response, mission)
        events = "".join(f"<li>{escape(event['event_type'])}: {escape(event['result'])}</li>" for event in timeline.body.get("events", []))
        approval_forms = "".join(
            f'<li>{escape(item["status"])} — {escape(item["scope"]["capability"])}'
            + (f'<form method="post" action="/praetorium/missions/{quote(mission_id)}/approvals/{quote(item["id"])}">'
               f'<input type="hidden" name="expected_mission_version" value="{mission.body["version"]}">'
               '<input name="reason" required maxlength="1000"><button name="decision" value="APPROVE">Approve</button><button name="decision" value="REJECT">Reject</button></form>' if item["status"] == "PENDING" else "")
            + "</li>" for item in approvals.body.get("approvals", [])
        ) or "<li>No approvals.</li>"
        command_form = f'''<form method="post" action="/praetorium/missions/{quote(mission_id)}/commands">
<input type="hidden" name="expected_version" value="{mission.body['version']}"><input name="idempotency_key" required placeholder="idempotency key"><input name="command_type" required placeholder="START"><textarea name="payload_json">{{}}</textarea><button>Submit command</button></form>'''
        body = f"<p>{escape(notice)}</p><h1>{escape(mission.body['title'])}</h1><p>{escape(mission.body['objective'])}</p><p>Status: {escape(mission.body['status'])}; version {mission.body['version']}</p>{command_form}<h2>Approvals</h2><ul>{approval_forms}</ul><h2>Timeline</h2><ul>{events}</ul><p><a href=\"{escape(self.tabula_console_url, quote=True)}\">Open Tabula Console</a></p>"
        return self._send(start_response, 200, self._page("Praetorium Mission", body))

    def _command(self, start_response, actor, mission_id, environ):
        form = self._form(environ)
        try:
            body = {"expected_version": int(form["expected_version"]), "idempotency_key": form["idempotency_key"], "command_type": form["command_type"], "payload": json.loads(form["payload_json"])}
        except (KeyError, ValueError, json.JSONDecodeError):
            return self._mission(start_response, actor, mission_id, "Invalid command form.")
        response = self.service.submit_command(actor=actor, mission_id=mission_id, body=body)
        return self._mission(start_response, actor, mission_id, response.body.get("code") or response.body.get("status", "Command submitted"))

    def _approval(self, start_response, actor, mission_id, approval_id, environ):
        form = self._form(environ)
        try:
            version = int(form.get("expected_mission_version", "0"))
        except ValueError:
            return self._mission(start_response, actor, mission_id, "Invalid approval form.")
        response = self.service.decide_approval(actor=actor, mission_id=mission_id, body={"approval_id": approval_id, "expected_mission_version": version, "decision": form.get("decision", ""), "reason": form.get("reason", "")})
        return self._mission(start_response, actor, mission_id, response.body.get("code") or response.body.get("status", "Approval recorded"))

    @staticmethod
    def _form(environ):
        raw = environ.get("wsgi.input", io.BytesIO()).read(int(environ.get("CONTENT_LENGTH") or 0)).decode("utf-8")
        return {key: values[-1] for key, values in parse_qs(raw).items()}

    def _error(self, start_response, response):
        return self._send(start_response, response.status_code, self._page("Praetorium error", f"<p>{escape(response.body.get('code', 'ERROR'))}</p>"))

    @staticmethod
    def _page(title, body):
        return f"<!doctype html><html><head><title>{escape(title)}</title></head><body>{body}</body></html>"

    @staticmethod
    def _send(start_response, status, body):
        raw = body.encode("utf-8"); start_response(f"{status} {'OK' if status == 200 else 'Error'}", [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(raw)))])
        return [raw]

    @staticmethod
    def _redirect(start_response, location):
        start_response("303 See Other", [("Location", location), ("Content-Length", "0")]); return [b""]
