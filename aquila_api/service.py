"""HTTP-shaped Aquila operations without a web-framework dependency.

The service intentionally accepts authenticated ``Principal`` values rather
than parsing OIDC tokens. An HTTP adapter can perform authentication and call
these methods without changing Mission semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from legion_kernel import (
    AuthorizationError,
    LegionKernel,
    Principal,
    PrincipalType,
    RoeLevel,
)


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    body: dict[str, Any]
    headers: dict[str, str]


class AquilaService:
    """OpenAPI operation adapter backed by a Mission kernel instance."""

    def __init__(self, kernel: LegionKernel | None = None) -> None:
        self.kernel = kernel or LegionKernel()

    def create_mission(self, *, actor: Principal, body: dict[str, Any]) -> ApiResponse:
        try:
            self._require_fields(body, "organization_id", "workspace_id", "title", "objective")
            self._validate_uuid(body["organization_id"])
            self._validate_uuid(body["workspace_id"])
            roe_level = RoeLevel(body.get("initial_roe_level", "OBSERVE"))
            mission = self.kernel.create_mission(
                actor=actor,
                organization_id=body["organization_id"],
                workspace_id=body["workspace_id"],
                title=body["title"],
                objective=body["objective"],
                roe_level=roe_level,
            )
        except (AuthorizationError, ValueError, TypeError, KeyError) as exc:
            return self._error(403 if str(exc) == "MISSION_CREATE_FORBIDDEN" else 422, str(exc))
        response = self._mission_payload(mission)
        return ApiResponse(
            status_code=201,
            body=response,
            headers={"Location": f"/missions/{mission.id}"},
        )

    def get_mission(self, *, actor: Principal, mission_id: str) -> ApiResponse:
        if not self._can_read(actor):
            return self._error(403, "FORBIDDEN")
        try:
            mission = self.kernel.get_mission(mission_id)
        except KeyError:
            return self._error(404, "NOT_FOUND")
        return ApiResponse(200, self._mission_payload(mission), {})

    def submit_command(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
        correlation_id: str | None = None,
    ) -> ApiResponse:
        try:
            self._require_fields(body, "expected_version", "idempotency_key", "command_type", "payload")
            if not isinstance(body["payload"], dict):
                raise TypeError("payload must be an object")
            result = self.kernel.submit_command(
                mission_id=mission_id,
                actor=actor,
                expected_version=int(body["expected_version"]),
                idempotency_key=str(body["idempotency_key"]),
                command_type=str(body["command_type"]),
                payload=body["payload"],
                requested_by=self._principal_from_body(body.get("requested_by"), actor),
                correlation_id=correlation_id,
            )
        except KeyError:
            return self._error(404, "NOT_FOUND")
        except (ValueError, TypeError) as exc:
            return self._error(422, str(exc))

        if result.error_code == "VERSION_CONFLICT":
            return self._error(409, result.error_code, current_version=result.mission_version)
        if result.error_code in {"FORBIDDEN", "ROE_DENIED"}:
            return self._error(403, result.error_code, current_version=result.mission_version)
        if result.error_code == "MISSION_TERMINAL":
            return self._error(409, result.error_code, current_version=result.mission_version)
        if result.status == "REJECTED":
            return self._error(422, result.error_code or "INVALID_REQUEST", current_version=result.mission_version)
        status_code = 202 if result.status == "AWAITING_APPROVAL" else 200
        return ApiResponse(status_code, self._command_payload(result), {})

    def decide_approval(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
    ) -> ApiResponse:
        try:
            self._require_fields(body, "approval_id", "expected_mission_version", "decision", "reason")
            approval = self.kernel.decide_approval(
                approval_id=str(body["approval_id"]),
                approver=actor,
                expected_mission_version=int(body["expected_mission_version"]),
                decision=str(body["decision"]),
                reason=str(body["reason"]),
            )
        except KeyError:
            return self._error(404, "NOT_FOUND")
        except AuthorizationError as exc:
            if str(exc) == "FORBIDDEN":
                return self._error(403, "FORBIDDEN")
            if str(exc) == "APPROVAL_STALE":
                return self._error(409, "APPROVAL_STALE")
            return self._error(409, str(exc))
        except (ValueError, TypeError) as exc:
            return self._error(422, str(exc))
        if approval.mission_id != mission_id:
            return self._error(404, "NOT_FOUND")
        return ApiResponse(200, self._approval_payload(approval), {})

    def get_timeline(
        self,
        *,
        actor: Principal,
        mission_id: str,
        limit: int = 50,
        after_sequence: int = 0,
    ) -> ApiResponse:
        if not self._can_read(actor):
            return self._error(403, "FORBIDDEN")
        if limit < 1 or limit > 200 or after_sequence < 0:
            return self._error(422, "INVALID_REQUEST")
        try:
            events = self.kernel.timeline(mission_id)
        except KeyError:
            return self._error(404, "NOT_FOUND")
        selected = [event for event in events if event.sequence > after_sequence]
        page = selected[:limit]
        has_more = len(selected) > len(page)
        next_cursor = str(page[-1].sequence) if has_more and page else None
        return ApiResponse(
            200,
            {
                "mission_id": mission_id,
                "events": [_audit_payload(event) for event in page],
                "next_cursor": next_cursor,
                "has_more": has_more,
            },
            {},
        )

    def cancel_mission(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
        correlation_id: str | None = None,
    ) -> ApiResponse:
        try:
            self._require_fields(body, "expected_version", "idempotency_key", "reason")
            result = self.kernel.submit_command(
                mission_id=mission_id,
                actor=actor,
                expected_version=int(body["expected_version"]),
                idempotency_key=str(body["idempotency_key"]),
                command_type="CANCEL",
                payload={"reason": body["reason"]},
                correlation_id=correlation_id,
            )
        except KeyError:
            return self._error(404, "NOT_FOUND")
        except (ValueError, TypeError) as exc:
            return self._error(422, str(exc))
        if result.error_code:
            status = 409 if result.error_code in {"VERSION_CONFLICT", "MISSION_TERMINAL"} else 403
            return self._error(status, result.error_code, current_version=result.mission_version)
        return self.get_mission(actor=actor, mission_id=mission_id)

    @staticmethod
    def _require_fields(body: dict[str, Any], *names: str) -> None:
        if not isinstance(body, dict):
            raise TypeError("body must be an object")
        missing = [name for name in names if name not in body]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

    @staticmethod
    def _validate_uuid(value: str) -> None:
        UUID(str(value))

    @staticmethod
    def _can_read(actor: Principal) -> bool:
        return actor.has_any_role("MISSION_OWNER", "OPERATOR", "OBSERVER", "APPROVER", "MISSION_WORKER")

    @staticmethod
    def _principal_from_body(value: Any, fallback: Principal) -> Principal:
        if value is None:
            return fallback
        if not isinstance(value, dict) or "type" not in value or "subject" not in value:
            raise ValueError("requested_by must contain type and subject")
        return Principal(
            type=PrincipalType(value["type"]),
            subject=str(value["subject"]),
            roles=frozenset(),
        )

    @staticmethod
    def _command_payload(result: Any) -> dict[str, Any]:
        return {
            "command_id": result.command_id,
            "mission_id": result.mission_id,
            "status": result.status,
            "mission_version": result.mission_version,
            "approval_id": result.approval_id,
            "error_code": result.error_code,
            "message": result.message,
        }

    @staticmethod
    def _mission_payload(mission: Any) -> dict[str, Any]:
        roe = mission.roe
        last_event_id = None
        return {
            "id": mission.id,
            "schema_version": "1.0",
            "organization_id": mission.organization_id,
            "workspace_id": mission.workspace_id,
            "project_id": None,
            "environment_id": None,
            "title": mission.title,
            "objective": mission.objective,
            "status": mission.status.value,
            "version": mission.version,
            "roe": {
                "schema_version": "1.0",
                "revision": roe.revision,
                "level": roe.level.value,
                "effective_at": roe.effective_at,
                "changed_by": _principal_payload(roe.changed_by),
                "allowed_capabilities": sorted(roe.allowed_capabilities),
                "denied_capabilities": sorted(roe.denied_capabilities),
                "approval": {
                    "required_for": sorted(roe.approval_required_for),
                    "minimum_approvals": 1 if roe.approval_required_for else 0,
                },
                "reason": roe.reason,
            },
            "constraints": [
                {
                    "id": constraint.id,
                    "text": constraint.text,
                    "severity": constraint.severity,
                    "added_at": constraint.added_at,
                    "added_by": _principal_payload(constraint.added_by),
                }
                for constraint in mission.constraints
            ],
            "participants": [],
            "labels": {},
            "active_execution": None,
            "last_event_id": last_event_id,
            "created_at": mission.created_at,
            "updated_at": mission.updated_at,
            "created_by": _principal_payload(mission.created_by),
        }

    @staticmethod
    def _approval_payload(approval: Any) -> dict[str, Any]:
        return {
            "id": approval.id,
            "schema_version": "1.0",
            "mission_id": approval.mission_id,
            "command_id": approval.command_id,
            "action_id": approval.action.id,
            "mission_version": approval.mission_version,
            "roe_revision": approval.roe_revision,
            "action_hash": approval.action_hash,
            "scope": {
                "capability": approval.action.capability,
                "side_effect_class": approval.action.side_effect_class,
                "target": approval.action.target,
                "environment_id": None,
            },
            "requested_by": _principal_payload(approval.requested_by),
            "approver": _principal_payload(approval.approver) if approval.approver else None,
            "status": approval.status,
            "decision_reason": approval.decision_reason,
            "requested_at": approval.action.requested_at,
            "decided_at": approval.decided_at,
            "expires_at": approval.expires_at,
            "consumed_at": approval.consumed_at,
        }

    @staticmethod
    def _error(status_code: int, code: str, *, current_version: int | None = None) -> ApiResponse:
        body = {
            "code": code,
            "message": code,
            "correlation_id": "service-generated",
            "current_version": current_version,
        }
        return ApiResponse(status_code, body, {})


def _principal_payload(principal: Principal | None) -> dict[str, Any] | None:
    if principal is None:
        return None
    return {"type": principal.type.value, "subject": principal.subject}


def _audit_payload(event: Any) -> dict[str, Any]:
    return {
        "id": event.id,
        "schema_version": "1.0",
        "sequence": event.sequence,
        "mission_id": event.mission_id,
        "mission_version": event.mission_version,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at,
        "recorded_at": event.occurred_at,
        "actor": _principal_payload(event.actor),
        "requested_by": None,
        "delegated_by": None,
        "executed_by": None,
        "resource": {"type": "Mission", "id": event.mission_id},
        "result": event.result,
        "command_id": event.command_id,
        "approval_id": event.approval_id,
        "correlation_id": event.correlation_id,
        "causation_id": event.causation_id,
        "data": event.data,
    }


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, frozenset | set):
        return sorted(_encode(item) for item in value)
    if isinstance(value, list | tuple):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    if is_dataclass(value):
        return {field.name: _encode(getattr(value, field.name)) for field in fields(value)}
    return value
