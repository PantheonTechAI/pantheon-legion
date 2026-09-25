"""Aquila service composition backed by the SQLite Mission repository."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import RLock
from typing import Any

from legion_kernel import AuthorizationError, LegionKernel, Principal, RoeLevel, WorkerKilled
from legion_kernel.kernel import Action, Approval, PrincipalType
from legion_store import SQLiteMissionStore
from legion_runtime import InMemoryDurableExecutionAdapter

from .authorization import DelegationGrant
from .investigation import PROFILE, InvestigationIntent, SQLiteInvestigationOutbox, intent_digest
from .service import ApiResponse, AquilaService, _principal_payload


def _serialized_operation(method):
    @wraps(method)
    def operation(self, *args, **kwargs):
        # Cover the in-memory mutation as well as its later database commit.
        with self._operation_lock:
            return method(self, *args, **kwargs)
    return operation


class PersistentAquilaService(AquilaService):
    """Rehydrate Aquila state from SQLite between service instances."""

    def __init__(self, database: str, *, investigation_subjects: tuple[str, str] | None = None) -> None:
        if investigation_subjects is not None and (
            len(investigation_subjects) != 2 or not all(investigation_subjects)
            or investigation_subjects[0] == investigation_subjects[1]
        ):
            raise ValueError("INVALID_INVESTIGATION_SUBJECTS")
        self.investigation_subjects = investigation_subjects
        self._operation_lock = RLock()
        self.store = SQLiteMissionStore(database)
        self.outbox = SQLiteInvestigationOutbox(self.store.connection)
        self._initialize_auxiliary_tables()
        execution_state = self._load_execution_state()
        super().__init__(
            LegionKernel(),
            execution=InMemoryDurableExecutionAdapter(execution_state.get("adapter")),
        )
        self.action_executions = dict(execution_state.get("action_executions", {}))
        self._restore()

    @_serialized_operation
    def close(self) -> None:
        self.store.close()

    def _persist_cognition_boundary(self, method_name, kwargs):
        context = kwargs.get("context")
        mission_id = context.mission_id if context else kwargs["mission_id"]
        with self.store.transaction():
            # Evaluate a fresh, isolated view of only this Mission and its grants.
            authority = AquilaService(authorization=self.authorization)
            mission = self.store.get_mission(mission_id)
            if mission is not None:
                authority.kernel.missions[mission_id] = mission
                authority.kernel.audit[mission_id] = self.store.get_audit(mission_id)
                authority.delegations = {grant.grant_id: grant for grant in self._list_delegations(mission_id)}
            before_sequence = len(authority.kernel.audit.get(mission_id, []))
            response = getattr(authority, method_name)(**kwargs)
            for event in authority.kernel.audit.get(mission_id, [])[before_sequence:]:
                self.store.append_audit(event)
        # Publish the committed target view while the whole-operation lock is held.
        # Other Missions and uncommitted mutations are never blanket-restored.
        if mission is not None:
            self.kernel.missions[mission_id] = mission
            self.kernel.audit[mission_id] = authority.kernel.audit[mission_id]
            self.delegations.update(authority.delegations)
        return response

    @_serialized_operation
    def authorize_cognition(self, **kwargs):
        return self._persist_cognition_boundary("authorize_cognition", kwargs)

    @_serialized_operation
    def record_cognition_outcome(self, **kwargs):
        return self._persist_cognition_boundary("record_cognition_outcome", kwargs)

    @_serialized_operation
    def authorize_grounded_knowledge_operation(self, **kwargs):
        return self._persist_cognition_boundary("authorize_grounded_knowledge_operation", kwargs)

    @_serialized_operation
    def record_grounded_knowledge_outcome(self, **kwargs):
        return self._persist_cognition_boundary("record_grounded_knowledge_outcome", kwargs)

    def _fresh_agent_authorization(self, method_name: str, kwargs: dict[str, Any]) -> ApiResponse:
        mission_id = str(kwargs["mission_id"])
        try:
            with self.store.transaction():
                self._refresh_mission(mission_id)
                mission = self.kernel.missions.get(mission_id)
                if mission is None:
                    return getattr(AquilaService, method_name)(self, **kwargs)
                before_version = mission.version
                before_sequence = len(self.kernel.audit[mission_id])
                response = getattr(AquilaService, method_name)(self, **kwargs)
                self._persist_operation(mission_id, before_version, before_sequence)
                return response
        except Exception:
            self._restore_all()
            raise

    @_serialized_operation
    def authorize_agent_assignment(self, **kwargs: Any) -> ApiResponse:
        return self._fresh_agent_authorization("authorize_agent_assignment", kwargs)

    @_serialized_operation
    def authorize_agent_resume(self, **kwargs: Any) -> ApiResponse:
        return self._fresh_agent_authorization("authorize_agent_resume", kwargs)

    @_serialized_operation
    def authorize_scout_context(self, **kwargs: Any) -> ApiResponse:
        return self._fresh_agent_authorization("authorize_scout_context", kwargs)

    @_serialized_operation
    def create_mission(self, *, actor: Principal, body: dict[str, Any]) -> ApiResponse:
        response = super().create_mission(actor=actor, body=body)
        if response.status_code == 201:
            mission_id = response.body["id"]
            mission = self.kernel.missions[mission_id]
            with self.store.transaction():
                self.store.save_mission(mission, expected_previous_version=None)
                for event in self.kernel.audit[mission_id]:
                    self.store.append_audit(event)
        return response

    @_serialized_operation
    def submit_command(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
        correlation_id: str | None = None,
    ) -> ApiResponse:
        if isinstance(body, dict) and body.get("command_type") == "REQUEST_INVESTIGATION":
            return self._submit_investigation(
                actor=actor, mission_id=mission_id, body=body,
                correlation_id=correlation_id,
            )
        try:
            with self.store.transaction():
                self._refresh_mission(mission_id)
                prior = self._stored_idempotency(mission_id, body, actor)
                if prior is not None:
                    return prior
                mission = self.kernel.missions.get(mission_id)
                before_version = mission.version if mission else None
                before_sequence = len(self.kernel.audit.get(mission_id, []))
                response = super().submit_command(
                    actor=actor, mission_id=mission_id, body=body,
                    correlation_id=correlation_id,
                )
                if mission_id in self.kernel.missions:
                    self._persist_operation(mission_id, before_version, before_sequence)
                    self._store_idempotency(mission_id, body, actor, response)
                    self._persist_execution_state()
                return response
        except Exception:
            self._restore_all()
            raise

    def _submit_investigation(
        self, *, actor: Principal, mission_id: str, body: dict[str, Any],
        correlation_id: str | None,
    ) -> ApiResponse:
        try:
            self._validate_command_submission(body)
        except (ValueError, TypeError) as exc:
            return self._error(422, str(exc))
        if body["payload"] != {"profile": PROFILE}:
            return self._error(422, "INVALID_COMMAND_PAYLOAD")
        if actor.type != PrincipalType.HUMAN or not actor.has_any_role("MISSION_OWNER"):
            return self._error(403, "MISSION_OWNER_REQUIRED")
        if self.investigation_subjects is None:
            return self._error(503, "INVESTIGATION_PROFILE_UNAVAILABLE")
        try:
            with self.store.transaction():
                self._refresh_mission(mission_id)
                mission = self.kernel.missions.get(mission_id)
                if mission is None:
                    return self._error(404, "NOT_FOUND")
                if (mission.created_by.type != actor.type
                        or mission.created_by.subject != actor.subject):
                    return self._error(403, "MISSION_OWNER_REQUIRED")
                prior = self._stored_idempotency(mission_id, body, actor)
                if prior is not None:
                    return prior
                if self.outbox.get_by_mission(mission_id) is not None:
                    return self._error(409, "INVESTIGATION_ALREADY_REQUESTED")
                before_version = mission.version
                before_sequence = len(self.kernel.audit[mission_id])
                response = super().submit_command(
                    actor=actor, mission_id=mission_id, body=body,
                    correlation_id=correlation_id,
                )
                if response.status_code != 200 or response.body["status"] != "ACCEPTED":
                    self._persist_operation(mission_id, before_version, before_sequence)
                    self._store_idempotency(mission_id, body, actor, response)
                    return response
                command_id = response.body["command_id"]
                expires_at = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat().replace("+00:00", "Z")
                centurion_subject, scout_subject = self.investigation_subjects
                centurion_grant_id = super().issue_delegation(
                    issuer=actor,
                    subject=Principal(PrincipalType.WORKLOAD, centurion_subject),
                    mission_id=mission_id,
                    allowed_operations=frozenset({"READ_MISSION", "INVOKE_COGNITION"}),
                    roe_ceiling=mission.roe.level,
                    expires_at=expires_at,
                )
                scout_grant_id = super().issue_delegation(
                    issuer=actor,
                    subject=Principal(PrincipalType.WORKLOAD, scout_subject),
                    mission_id=mission_id,
                    allowed_operations=frozenset({"READ_MISSION", "READ_KNOWLEDGE", "INVOKE_COGNITION"}),
                    roe_ceiling=mission.roe.level,
                    expires_at=expires_at,
                )
                current = self.kernel.missions[mission_id]
                intent = InvestigationIntent(
                    command_id=command_id, mission_id=mission_id,
                    organization_id=current.organization_id,
                    workspace_id=current.workspace_id, profile=PROFILE,
                    intent_digest=intent_digest(
                        command_id=command_id, mission_id=mission_id,
                        organization_id=current.organization_id,
                        workspace_id=current.workspace_id,
                        objective=current.objective, profile=PROFILE,
                    ),
                    mission_version=current.version,
                    centurion_grant_id=centurion_grant_id,
                    scout_grant_id=scout_grant_id,
                    expires_at=expires_at,
                    correlation_id=command_id,
                    requested_by=actor.subject,
                )
                self._persist_operation(mission_id, before_version, before_sequence)
                self._persist_delegation(centurion_grant_id)
                self._persist_delegation(scout_grant_id)
                self.outbox.insert(intent)
                result = ApiResponse(200, {
                    **response.body, "investigation_intent_id": command_id,
                    "delivery_status": intent.status,
                }, response.headers)
                self._store_idempotency(mission_id, body, actor, result)
                return result
        except Exception:
            self._restore_all()
            raise

    def _refresh_mission(self, mission_id: str) -> None:
        mission = self.store.get_mission(mission_id)
        if mission is None:
            return
        self.kernel.missions[mission_id] = mission
        self.kernel.audit[mission_id] = self.store.get_audit(mission_id)
        self.delegations = {
            grant_id: grant for grant_id, grant in self.delegations.items()
            if grant.mission_id != mission_id
        }
        self.delegations.update({
            grant.grant_id: grant for grant in self._list_delegations(mission_id)
        })

    def _restore_all(self) -> None:
        self.kernel = LegionKernel()
        self.delegations = {}
        self._restore()

    @_serialized_operation
    def get_mission(self, *, actor: Principal, mission_id: str) -> ApiResponse:
        with self.store.transaction():
            self._refresh_mission(mission_id)
            return super().get_mission(actor=actor, mission_id=mission_id)

    @_serialized_operation
    def get_timeline(self, *, actor: Principal, mission_id: str,
                     limit: int = 50, after_sequence: int = 0) -> ApiResponse:
        with self.store.transaction():
            self._refresh_mission(mission_id)
            return super().get_timeline(
                actor=actor, mission_id=mission_id, limit=limit,
                after_sequence=after_sequence,
            )

    @_serialized_operation
    def get_investigation(self, *, actor: Principal, mission_id: str) -> ApiResponse:
        authorized = self.get_mission(actor=actor, mission_id=mission_id)
        if authorized.status_code != 200:
            return authorized
        creator = authorized.body["created_by"]
        if creator["type"] != actor.type.value or creator["subject"] != actor.subject:
            return self._error(403, "MISSION_OWNER_REQUIRED")
        intent = self.outbox.get_by_mission(mission_id)
        if intent is None:
            return ApiResponse(200, {
                "requested": False,
                "available": self.investigation_subjects is not None,
            }, {})
        return ApiResponse(200, {
            "requested": True,
            "command_id": intent.command_id,
            "status": intent.status,
            "last_error_code": intent.last_error_code,
            "intake_id": intent.intake_id,
            "profile": intent.profile,
            "expires_at": intent.expires_at,
        }, {})

    @_serialized_operation
    def decide_approval(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
    ) -> ApiResponse:
        before_version = self.kernel.missions[mission_id].version
        before_sequence = len(self.kernel.audit.get(mission_id, []))
        response = super().decide_approval(actor=actor, mission_id=mission_id, body=body)
        if mission_id in self.kernel.missions:
            with self.store.transaction():
                self._persist_operation(mission_id, before_version, before_sequence)
                for approval in self.kernel.approvals.values():
                    if approval.mission_id == mission_id:
                        self._persist_approval(approval.id)
        return response

    @_serialized_operation
    def execute_action(
        self,
        *,
        mission_id: str,
        action_id: str,
        worker: Principal,
        delegation_id: str | None = None,
        fail_after_side_effect: bool = False,
    ) -> str:
        mission = self.kernel.missions[mission_id]
        before_version = mission.version
        before_sequence = len(self.kernel.audit[mission_id])
        try:
            return super().execute_action(
                mission_id=mission_id,
                action_id=action_id,
                worker=worker,
                delegation_id=delegation_id,
                fail_after_side_effect=fail_after_side_effect,
            )
        finally:
            with self.store.transaction():
                self._persist_operation(mission_id, before_version, before_sequence)
                self._persist_side_effect(mission_id, action_id)
                for approval in self.kernel.approvals.values():
                    if approval.mission_id == mission_id:
                        self._persist_approval(approval.id)
                self._persist_execution_state()

    @_serialized_operation
    def issue_delegation(self, **kwargs: Any) -> str:
        mission_id = str(kwargs["mission_id"])
        error = None
        delegation_id = None
        try:
            with self.store.transaction():
                self._refresh_mission(mission_id)
                before_version = self.kernel.missions[mission_id].version
                before_sequence = len(self.kernel.audit[mission_id])
                try:
                    delegation_id = super().issue_delegation(**kwargs)
                except AuthorizationError as exc:
                    error = exc
                self._persist_operation(mission_id, before_version, before_sequence)
                if delegation_id is not None:
                    self._persist_delegation(delegation_id)
        except Exception:
            self._restore_all()
            raise
        if error is not None:
            raise error
        assert delegation_id is not None
        return delegation_id

    @_serialized_operation
    def revoke_delegation(self, **kwargs: Any) -> None:
        mission_id = str(kwargs["mission_id"])
        delegation_id = str(kwargs["delegation_id"])
        error = None
        try:
            with self.store.transaction():
                self._refresh_mission(mission_id)
                before_version = self.kernel.missions[mission_id].version
                before_sequence = len(self.kernel.audit[mission_id])
                try:
                    super().revoke_delegation(**kwargs)
                except AuthorizationError as exc:
                    error = exc
                self._persist_operation(mission_id, before_version, before_sequence)
                if delegation_id in self.delegations:
                    self._persist_delegation(delegation_id)
        except Exception:
            self._restore_all()
            raise
        if error is not None:
            raise error

    @_serialized_operation
    def invoke_read_tool(self, **kwargs: Any) -> Any:
        """Persist the material authorization and result audit facts for a tool read."""
        mission_id = str(kwargs["mission_id"])
        mission = self.kernel.missions[mission_id]
        before_version = mission.version
        before_sequence = len(self.kernel.audit[mission_id])
        try:
            return super().invoke_read_tool(**kwargs)
        finally:
            with self.store.transaction():
                self._persist_operation(mission_id, before_version, before_sequence)

    @_serialized_operation
    def retrieve_knowledge(self, **kwargs: Any) -> Any:
        """Preserve legacy knowledge authorization audit alongside fresh boundaries."""
        return self._persist_federated_read("retrieve_knowledge", kwargs)

    @_serialized_operation
    def retrieve_federated_corpus(self, **kwargs: Any) -> Any:
        """Persist the authorization and terminal audit facts for a Tabula corpus read."""
        return self._persist_federated_read("retrieve_federated_corpus", kwargs)

    @_serialized_operation
    def retrieve_federated_registry(self, **kwargs: Any) -> Any:
        """Persist the authorization and terminal audit facts for a Tabula Registry read."""
        return self._persist_federated_read("retrieve_federated_registry", kwargs)

    @_serialized_operation
    def run_scout(self, **kwargs: Any) -> Any:
        """Persist the digest-only model invocation fact when a Scout uses one."""
        mission_id = str(kwargs["mission_id"])
        mission = self.kernel.missions[mission_id]
        before_version = mission.version
        before_sequence = len(self.kernel.audit[mission_id])
        try:
            return super().run_scout(**kwargs)
        finally:
            with self.store.transaction():
                self._persist_operation(mission_id, before_version, before_sequence)

    def _persist_federated_read(self, method_name: str, kwargs: dict[str, Any]) -> Any:
        mission_id = str(kwargs["mission_id"])
        mission = self.kernel.missions[mission_id]
        before_version = mission.version
        before_sequence = len(self.kernel.audit[mission_id])
        try:
            method = getattr(super(), method_name)
            return method(**kwargs)
        finally:
            with self.store.transaction():
                self._persist_operation(mission_id, before_version, before_sequence)

    @_serialized_operation
    def cancel_mission(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
        correlation_id: str | None = None,
    ) -> ApiResponse:
        response = self.submit_command(
            actor=actor,
            mission_id=mission_id,
            body={
                "expected_version": body.get("expected_version"),
                "idempotency_key": body.get("idempotency_key"),
                "command_type": "CANCEL",
                "payload": {},
            },
            correlation_id=correlation_id,
        )
        if response.status_code not in {200, 202}:
            return response
        return self.get_mission(actor=actor, mission_id=mission_id)

    def _restore(self) -> None:
        for mission_id in self.store.list_mission_ids():
            mission = self.store.get_mission(mission_id)
            self.kernel.missions[mission_id] = mission
            self.kernel.audit[mission_id] = self.store.get_audit(mission_id)
            for approval in self._list_persisted_approvals(mission_id):
                self.kernel.approvals[approval.id] = approval
            for action_id in self._list_side_effects(mission_id):
                self.kernel.side_effects[action_id] = self._get_side_effect(action_id)
            for delegation in self._list_delegations(mission_id):
                self.delegations[delegation.grant_id] = delegation

    def _persist_operation(
        self,
        mission_id: str,
        before_version: int | None,
        before_sequence: int,
    ) -> None:
        mission = self.kernel.missions[mission_id]
        events = self.kernel.audit[mission_id][before_sequence:]
        if not events:
            return
        if before_version is None:
            self.store.save_mission(mission, expected_previous_version=None)
        elif mission.version != before_version:
            self.store.save_mission(mission, expected_previous_version=before_version)
        for event in events:
            self.store.append_audit(event)
        for approval in self.kernel.approvals.values():
            if approval.mission_id == mission_id:
                self._persist_approval(approval.id)

    def _initialize_auxiliary_tables(self) -> None:
        with self.store.connection:
            self.store.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS persistent_approvals (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS persistent_side_effects (
                    action_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    count INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS persistent_execution_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS persistent_delegations (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )
            self.outbox.initialize()

    def _persist_approval(self, approval_id: str) -> None:
        approval = self.kernel.approvals[approval_id]
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO persistent_approvals (id, mission_id, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (approval.id, approval.mission_id, json.dumps(_approval_payload(approval), sort_keys=True)),
            )

    def _persist_delegation(self, delegation_id: str) -> None:
        delegation = self.delegations[delegation_id]
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO persistent_delegations (id, mission_id, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (delegation.grant_id, delegation.mission_id,
                 json.dumps(_delegation_payload(delegation), sort_keys=True)),
            )

    def _list_delegations(self, mission_id: str) -> list[DelegationGrant]:
        rows = self.store.connection.execute(
            "SELECT payload FROM persistent_delegations WHERE mission_id = ?", (mission_id,)
        ).fetchall()
        return [_delegation_from_payload(json.loads(row["payload"])) for row in rows]

    def _list_persisted_approvals(self, mission_id: str) -> list[Approval]:
        rows = self.store.connection.execute(
            "SELECT payload FROM persistent_approvals WHERE mission_id = ?", (mission_id,)
        ).fetchall()
        return [_approval_from_payload(json.loads(row["payload"])) for row in rows]

    def _persist_side_effect(self, mission_id: str, action_id: str) -> None:
        count = self.kernel.side_effects.get(action_id, 0)
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO persistent_side_effects (action_id, mission_id, count)
                VALUES (?, ?, ?)
                ON CONFLICT(action_id) DO UPDATE SET count = excluded.count
                """,
                (action_id, mission_id, count),
            )

    def _load_execution_state(self) -> dict[str, Any]:
        row = self.store.connection.execute(
            "SELECT payload FROM persistent_execution_state WHERE id = 1"
        ).fetchone()
        return json.loads(row["payload"]) if row else {}

    def _persist_execution_state(self) -> None:
        state = {"adapter": self.execution.snapshot(), "action_executions": self.action_executions}
        with self.store.transaction():
            self.store.connection.execute(
                "INSERT INTO persistent_execution_state (id, payload) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET payload = excluded.payload",
                (json.dumps(state, sort_keys=True),),
            )

    def _list_side_effects(self, mission_id: str) -> list[str]:
        rows = self.store.connection.execute(
            "SELECT action_id FROM persistent_side_effects WHERE mission_id = ?", (mission_id,)
        ).fetchall()
        return [row["action_id"] for row in rows]

    def _get_side_effect(self, action_id: str) -> int:
        row = self.store.connection.execute(
            "SELECT count FROM persistent_side_effects WHERE action_id = ?", (action_id,)
        ).fetchone()
        return int(row["count"]) if row else 0

    def _stored_idempotency(
        self,
        mission_id: str,
        body: dict[str, Any],
        actor: Principal,
    ) -> ApiResponse | None:
        key = body.get("idempotency_key") if isinstance(body, dict) else None
        if not key:
            return None
        record = self.store.get_idempotency(mission_id=mission_id, idempotency_key=str(key))
        if record is None:
            return None
        fingerprint = _request_fingerprint(body, actor)
        if record["fingerprint"] != fingerprint:
            return self._error(409, "IDEMPOTENCY_KEY_REUSE")
        return ApiResponse(
            status_code=record["result"]["status_code"],
            body=record["result"]["body"],
            headers=record["result"].get("headers", {}),
        )

    def _store_idempotency(
        self,
        mission_id: str,
        body: dict[str, Any],
        actor: Principal,
        response: ApiResponse,
    ) -> None:
        key = body.get("idempotency_key")
        if not key:
            return
        fingerprint = _request_fingerprint(body, actor)
        self.store.put_idempotency(
            mission_id=mission_id,
            idempotency_key=str(key),
            fingerprint=fingerprint,
            result={
                "status_code": response.status_code,
                "body": response.body,
                "headers": response.headers,
            },
        )


def _approval_payload(approval: Approval) -> dict[str, Any]:
    return {
        "id": approval.id,
        "mission_id": approval.mission_id,
        "command_id": approval.command_id,
        "action": {
            "id": approval.action.id,
            "command_id": approval.action.command_id,
            "capability": approval.action.capability,
            "arguments": approval.action.arguments,
            "target": approval.action.target,
            "side_effect_class": approval.action.side_effect_class,
            "requested_by": _principal_payload(approval.action.requested_by),
            "requested_at": approval.action.requested_at,
        },
        "mission_version": approval.mission_version,
        "roe_revision": approval.roe_revision,
        "action_hash": approval.action_hash,
        "requested_by": _principal_payload(approval.requested_by),
        "status": approval.status,
        "approver": _principal_payload(approval.approver),
        "decision_reason": approval.decision_reason,
        "decided_at": approval.decided_at,
        "expires_at": approval.expires_at,
        "consumed_at": approval.consumed_at,
    }


def _approval_from_payload(payload: dict[str, Any]) -> Approval:
    action = payload["action"]
    return Approval(
        id=payload["id"],
        mission_id=payload["mission_id"],
        command_id=payload["command_id"],
        action=Action(
            id=action["id"],
            command_id=action.get("command_id", payload["command_id"]),
            capability=action["capability"],
            arguments=action["arguments"],
            target=action["target"],
            side_effect_class=action["side_effect_class"],
            requested_by=Principal(
                PrincipalType(action["requested_by"]["type"]),
                action["requested_by"]["subject"],
            ),
            requested_at=action["requested_at"],
        ),
        mission_version=payload["mission_version"],
        roe_revision=payload["roe_revision"],
        action_hash=payload["action_hash"],
        requested_by=Principal(
            PrincipalType(payload["requested_by"]["type"]),
            payload["requested_by"]["subject"],
        ),
        status=payload["status"],
        approver=(
            Principal(PrincipalType(payload["approver"]["type"]), payload["approver"]["subject"])
            if payload["approver"]
            else None
        ),
        decision_reason=payload["decision_reason"],
        decided_at=payload["decided_at"],
        expires_at=payload["expires_at"],
        consumed_at=payload["consumed_at"],
    )


def _request_fingerprint(body: dict[str, Any], actor: Principal) -> str:
    return json.dumps(
        {
            "actor": actor.subject,
            "command_type": body.get("command_type"),
            "expected_version": body.get("expected_version"),
            "payload": body.get("payload"),
        },
        sort_keys=True,
    )


def _delegation_payload(grant: DelegationGrant) -> dict[str, Any]:
    def principal(principal: Principal | None) -> dict[str, Any] | None:
        if principal is None:
            return None
        return {"type": principal.type.value, "subject": principal.subject, "roles": sorted(principal.roles)}

    return {
        "grant_id": grant.grant_id, "issuer": principal(grant.issuer), "subject": principal(grant.subject),
        "mission_id": grant.mission_id, "allowed_operations": sorted(grant.allowed_operations),
        "roe_ceiling": grant.roe_ceiling.value, "expires_at": grant.expires_at, "issued_at": grant.issued_at,
        "revoked": grant.revoked, "revoked_at": grant.revoked_at,
        "revoked_by": principal(grant.revoked_by), "revocation_reason": grant.revocation_reason,
    }


def _delegation_from_payload(payload: dict[str, Any]) -> DelegationGrant:
    def principal(value: dict[str, Any] | None) -> Principal | None:
        if value is None:
            return None
        return Principal(PrincipalType(value["type"]), value["subject"], frozenset(value.get("roles", [])))

    issuer = principal(payload["issuer"])
    subject = principal(payload["subject"])
    assert issuer is not None and subject is not None
    return DelegationGrant(
        grant_id=payload["grant_id"], issuer=issuer, subject=subject, mission_id=payload["mission_id"],
        allowed_operations=frozenset(payload["allowed_operations"]), roe_ceiling=RoeLevel(payload["roe_ceiling"]),
        expires_at=payload["expires_at"], issued_at=payload["issued_at"], revoked=payload["revoked"],
        revoked_at=payload.get("revoked_at"), revoked_by=principal(payload.get("revoked_by")),
        revocation_reason=payload.get("revocation_reason"),
    )
