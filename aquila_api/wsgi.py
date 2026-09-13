"""Minimal standard-library WSGI adapter for the Aquila OpenAPI surface."""

from __future__ import annotations

import io
import json
from urllib.parse import parse_qs

from .auth import AuthenticationError, BearerAuthenticator
from .service import ApiResponse, AquilaService


class AquilaWSGIApp:
    """Route the first Aquila endpoints without coupling the kernel to WSGI."""

    def __init__(self, service: AquilaService, authenticator: BearerAuthenticator) -> None:
        self.service = service
        self.authenticator = authenticator

    def __call__(self, environ, start_response):
        try:
            actor = self.authenticator.authenticate(environ.get("HTTP_AUTHORIZATION"))
        except AuthenticationError as exc:
            return self._send(start_response, 401, {"code": str(exc), "message": str(exc)})

        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "")
        try:
            body = self._read_json(environ)
        except ValueError as exc:
            return self._send(start_response, 400, {"code": "INVALID_REQUEST", "message": str(exc)})

        try:
            response = self._dispatch(environ, actor, method, path, body)
        except KeyError:
            response = ApiResponse(404, {"code": "NOT_FOUND", "message": "NOT_FOUND"}, {})
        except (TypeError, ValueError) as exc:
            response = ApiResponse(422, {"code": "INVALID_REQUEST", "message": str(exc)}, {})
        except Exception:
            response = ApiResponse(500, {"code": "INTERNAL_ERROR", "message": "INTERNAL_ERROR"}, {})
        return self._send(start_response, response.status_code, response.body, response.headers)

    def _dispatch(self, environ, actor, method, path, body) -> ApiResponse:
        segments = [segment for segment in path.split("/") if segment]
        correlation_id = environ.get("HTTP_X_CORRELATION_ID")
        if segments == ["missions"] and method == "POST":
            return self.service.create_mission(actor=actor, body=body)
        if len(segments) == 2 and segments[0] == "missions":
            mission_id = segments[1]
            if method == "GET":
                return self.service.get_mission(actor=actor, mission_id=mission_id)
        if len(segments) == 3 and segments[0] == "missions":
            mission_id, action = segments[1:]
            if action == "commands" and method == "POST":
                return self.service.submit_command(
                    actor=actor,
                    mission_id=mission_id,
                    body=body,
                    correlation_id=correlation_id,
                )
            if action == "approvals" and method == "POST":
                return self.service.decide_approval(
                    actor=actor,
                    mission_id=mission_id,
                    body=body,
                )
            if action == "timeline" and method == "GET":
                query = parse_qs(environ.get("QUERY_STRING", ""))
                return self.service.get_timeline(
                    actor=actor,
                    mission_id=mission_id,
                    limit=int(query.get("limit", [50])[0]),
                    after_sequence=int(query.get("after_sequence", [0])[0]),
                )
            if action == "cancel" and method == "POST":
                return self.service.cancel_mission(
                    actor=actor,
                    mission_id=mission_id,
                    body=body,
                    correlation_id=correlation_id,
                )
        return ApiResponse(404, {"code": "NOT_FOUND", "message": "NOT_FOUND"}, {})

    @staticmethod
    def _read_json(environ) -> dict:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        if length == 0:
            return {}
        raw = environ.get("wsgi.input", io.BytesIO()).read(length)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    @staticmethod
    def _send(start_response, status_code: int, body: dict, headers: dict | None = None):
        reasons = {
            200: "OK",
            201: "Created",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            409: "Conflict",
            422: "Unprocessable Entity",
            500: "Internal Server Error",
        }
        encoded = json.dumps(body, sort_keys=True).encode("utf-8")
        output_headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(encoded)),
        }
        output_headers.update(headers or {})
        start_response(
            f"{status_code} {reasons.get(status_code, 'Response')}",
            list(output_headers.items()),
        )
        return [encoded]
