"""Aquila service composition backed by the SQLite Mission repository."""

from __future__ import annotations

import json
from typing import Any

from legion_kernel import AuthorizationError, LegionKernel, Principal, WorkerKilled
from legion_kernel.kernel import Action, Approval, PrincipalType
from legion_store import SQLiteMissionStore
from legion_runtime import InMemoryDurableExecutionAdapter

from .authorization import DelegationGrant
from .service import ApiResponse, AquilaService, _principal_payload


class PersistentAquilaService(AquilaService):
    """Rehydrate Aquila state from SQLite between service instances."""

    def __init__(self, database: str) -> None:
        self.store = SQLiteMissionStore(database)
        self._initialize_auxiliary_tables()
        execution_state = self._load_execution_state()
        super().__init__(
            LegionKernel(),
            execution=InMemoryDurableExecutionAdapter(execution_state.get("adapter")),
        )
        self.action_executions = dict(execution_state.get("action_executions", {}))
        self._restore()

    def close(self) -> None:
        self.store.close()

    def create_mission(self, *, actor: Principal, body: dict[str, Any]) -> ApiResponse:
        response = super().create_mission(actor=actor, body=body)
        if response.status_code == 201:
            mission_id = response.body["id"]
            mission = self.kernel.missions[mission_id]
            self.store.save_mission(mission, expected_previous_version=None)
            for event in self.kernel.audit[mission_id]:
                self.store.append_audit(event)
        return response

    def submit_command(
        self,
        *,
        actor: Principal,
        mission_id: str,
        body: dict[str, Any],
        correlation_id: str | None = None,
    ) -> ApiResponse:
        prior = self._stored_idempotency(mission_id, body, actor)
        if prior is not None:
            return prior
        mission = self.kernel.missions.get(mission_id)
        before_version = mission.version if mission else None
        before_sequence = len(self.kernel.audit.get(mission_id, []))
        response = super().submit_command(
            actor=actor,
            mission_id=mission_id,
            body=body,
            correlation_id=correlation_id,
        )
        if mission_id in self.kernel.missions:
            self._persist_operation(mission_id, before_version, before_sequence)
            self._store_idempotency(mission_id, body, actor, response)
            self._persist_execution_state()
        return response

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
            self._persist_operation(mission_id, before_version, before_sequence)
            for approval in self.kernel.approvals.values():
                if approval.mission_id == mission_id:
                    self._persist_approval(approval.id)
        return response

    def execute_action(
        self,
        *,
        mission_id: str,
        action_id: str,
        worker: Principal,
        delegation: DelegationGrant | None = None,
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
                delegation=delegation,
                fail_after_side_effect=fail_after_side_effect,
            )
        finally:
            self._persist_operation(mission_id, before_version, before_sequence)
            self._persist_side_effect(mission_id, action_id)
            for approval in self.kernel.approvals.values():
                if approval.mission_id == mission_id:
                    self._persist_approval(approval.id)
            self._persist_execution_state()

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
                "payload": {"reason": body.get("reason")},
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
                """
            )

    def _persist_approval(self, approval_id: str) -> None:
        approval = self.kernel.approvals[approval_id]
        with self.store.connection:
            self.store.connection.execute(
                """
                INSERT INTO persistent_approvals (id, mission_id, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (approval.id, approval.mission_id, json.dumps(_approval_payload(approval), sort_keys=True)),
            )

    def _list_persisted_approvals(self, mission_id: str) -> list[Approval]:
        rows = self.store.connection.execute(
            "SELECT payload FROM persistent_approvals WHERE mission_id = ?", (mission_id,)
        ).fetchall()
        return [_approval_from_payload(json.loads(row["payload"])) for row in rows]

    def _persist_side_effect(self, mission_id: str, action_id: str) -> None:
        count = self.kernel.side_effects.get(action_id, 0)
        with self.store.connection:
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
        with self.store.connection:
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
        try:
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
        except Exception:
            pass


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
