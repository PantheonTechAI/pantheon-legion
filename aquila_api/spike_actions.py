"""Opt-in Aquila authority for the single synthetic Strands-spike action.

Not registered by the API application. Only the trusted fixture composition
may construct this adapter; callers carry authenticated Runtime scope, never
model-supplied identities. No production tool or arbitrary argument is accepted.
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
from uuid import uuid4

from legion_kernel import AuthorizationError, Principal, PrincipalType
from .authorization import Decision
from .persistent import _approval_payload
from .service import AquilaService


CAPABILITY = "fixture.record_review"


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def action_digest(arguments):
    if type(arguments) is not dict or arguments != {"marker": "reviewed"}:
        raise AuthorizationError("SPIKE_ACTION_SCHEMA_REFUSED")
    return canonical_digest({"version": 1, "capability": CAPABILITY, "arguments": arguments})


@dataclass(frozen=True)
class ActionScope:
    mission_id: str
    agent_id: str
    assignment_id: str
    work_item_id: str
    attempt_id: str
    binding_id: str
    attempt_version: int
    execution_id: str
    grant_id: str
    logical_operation_id: str
    correlation_id: str
    workload: Principal

    def payload(self):
        if self.workload.type != PrincipalType.WORKLOAD or not self.workload.subject:
            raise AuthorizationError("SPIKE_WORKLOAD_REQUIRED")
        result = asdict(self)
        result["workload"] = {"type": self.workload.type.value, "subject": self.workload.subject}
        return result


class SpikeActionAuthority:
    """Fresh target-Mission view, existing grants/approvals, durable permits."""

    def __init__(self, aquila):
        self.aquila = aquila
        with aquila._operation_lock, aquila.store.transaction():
            aquila.store.connection.execute("""CREATE TABLE IF NOT EXISTS spike_action_permits (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL
                CHECK(status IN ('ISSUED','CONSUMED')))""")
            aquila.store.connection.execute("""CREATE TABLE IF NOT EXISTS spike_action_receipts (
                logical_operation_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
                action_digest TEXT NOT NULL, receipt_id TEXT NOT NULL)""")

    @contextmanager
    def _view(self, scope):
        with self.aquila._operation_lock:
            with self._target_view(scope) as value:
                yield value

    @contextmanager
    def _target_view(self, scope):
        scope.payload()
        aquila = self.aquila
        error = None
        with aquila._operation_lock, aquila.store.transaction():
            view = AquilaService(authorization=aquila.authorization)
            view.kernel.clock = aquila.kernel.clock
            mission = aquila.store.get_mission(scope.mission_id)
            if mission is None:
                raise AuthorizationError("SPIKE_MISSION_UNKNOWN")
            view.kernel.missions[mission.id] = mission
            view.kernel.audit[mission.id] = aquila.store.get_audit(mission.id)
            view.kernel.approvals = {item.id: item for item in aquila._list_persisted_approvals(mission.id)}
            view.delegations = {item.grant_id: item for item in aquila._list_delegations(mission.id)}
            version, sequence = mission.version, len(view.kernel.audit[mission.id])
            try:
                yield view, mission
            except AuthorizationError as exc:
                # Preserve denial/expiry audit only. Every operation must finish
                # all AuthorizationError-producing checks BEFORE mutating permit
                # or receipt records. Other errors roll back the whole transaction.
                error = exc
            if mission.version != version:
                aquila.store.save_mission(mission, expected_previous_version=version)
            for event in view.kernel.audit[mission.id][sequence:]:
                aquila.store.append_audit(event)
            for approval in view.kernel.approvals.values():
                aquila.store.connection.execute("""INSERT INTO persistent_approvals (id, mission_id, payload)
                    VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload""",
                    (approval.id, mission.id, json.dumps(_approval_payload(approval), sort_keys=True)))
        # Publish only this committed Mission; never restore unrelated state.
        with aquila._operation_lock:
            aquila.kernel.missions[mission.id] = mission
            aquila.kernel.audit[mission.id] = view.kernel.audit[mission.id]
            aquila.kernel.approvals.update(view.kernel.approvals)
            aquila.delegations.update(view.delegations)
        if error is not None:
            raise error

    def _receipt(self, scope):
        return self.aquila.store.connection.execute(
            "SELECT * FROM spike_action_receipts WHERE logical_operation_id=?",
            (scope.logical_operation_id,)).fetchone()

    def _check_action(self, mission, scope, arguments):
        action = mission.actions.get(scope.logical_operation_id)
        if (action is None or action.capability != CAPABILITY or action.arguments != arguments
                or action.target != "isolated-spike-ledger" or action.side_effect_class != "MUTATION"):
            raise AuthorizationError("SPIKE_ACTION_MISMATCH")
        return action

    def _decision(self, view, mission, scope, *, approval_present=False):
        return view._workload_decision(principal=scope.workload, mission_id=mission.id,
            operation="EXECUTE_ACTION", roe_level=mission.roe.level, mission_status=mission.status,
            delegation_id=scope.grant_id, side_effect_class="MUTATION", capability=CAPABILITY,
            approval_present=approval_present)

    def _dispatch_check(self, view, mission, scope, arguments):
        action = self._check_action(mission, scope, arguments)
        if view.kernel._capability_denied(mission.roe, action):
            raise AuthorizationError("ROE_DENIED")
        receipt = self._receipt(scope)
        if receipt and (receipt["mission_id"] != scope.mission_id
                        or receipt["action_digest"] != action_digest(arguments)):
            raise AuthorizationError("SPIKE_RECEIPT_SCOPE_MISMATCH")
        approval = next((item for item in view.kernel.approvals.values()
                         if item.action.id == scope.logical_operation_id), None)
        decision = self._decision(view, mission, scope, approval_present=bool(
            approval and (approval.status == "APPROVED" or (receipt and approval.status == "CONSUMED"))))
        if decision.decision != Decision.ALLOW:
            raise AuthorizationError(decision.reason)
        if mission.status.value not in {"ACTIVE", "AWAITING_APPROVAL"}:
            raise AuthorizationError("SPIKE_MISSION_NOT_EXECUTABLE")
        if receipt is None:
            view.kernel.validate_action_execution(mission_id=mission.id,
                action_id=scope.logical_operation_id, worker=scope.workload)
        return decision, approval, receipt

    def propose(self, scope, arguments):
        action_digest(arguments)
        with self._view(scope) as (view, mission):
            decision = self._decision(view, mission, scope)
            if decision.decision != Decision.ALLOW and decision.reason != "APPROVAL_REQUIRED":
                raise AuthorizationError(decision.reason)
            if scope.logical_operation_id not in mission.actions:
                result = view.kernel.submit_command(mission_id=mission.id, actor=scope.workload,
                    requested_by=scope.workload, expected_version=mission.version,
                    idempotency_key="spike-action:" + scope.logical_operation_id,
                    command_type="REQUEST_ACTION", correlation_id=scope.correlation_id,
                    payload={"action_id": scope.logical_operation_id, "capability": CAPABILITY,
                             "arguments": arguments, "target": "isolated-spike-ledger", "side_effect_class": "MUTATION"})
                if result.status not in {"ACCEPTED", "AWAITING_APPROVAL"}:
                    raise AuthorizationError(result.error_code or "SPIKE_PROPOSAL_REFUSED")
            self._check_action(mission, scope, arguments)
            approval = next((item for item in view.kernel.approvals.values()
                             if item.action.id == scope.logical_operation_id), None)
            return {"status": approval.status if approval else "NOT_REQUIRED",
                    "approval_id": approval.id if approval else None}

    def issue(self, scope, arguments):
        digest = action_digest(arguments)
        with self._view(scope) as (view, mission):
            decision, approval, receipt = self._dispatch_check(view, mission, scope, arguments)
            issued = view.authorization.clock()
            expiry = min(datetime.fromisoformat(issued) + timedelta(seconds=60),
                         datetime.fromisoformat(view.delegations[scope.grant_id].expires_at))
            if approval and receipt is None:
                expiry = min(expiry, datetime.fromisoformat(approval.expires_at))
            payload = {"version": 1, "scope": scope.payload(), "capability": CAPABILITY,
                       "action_digest": digest, "mission_version": mission.version,
                       "roe_revision": mission.roe.revision, "policy_version": decision.policy_version,
                       "decision_id": decision.decision_id, "issued_at": issued,
                       "expires_at": expiry.isoformat().replace("+00:00", "Z"), "nonce": str(uuid4()),
                       "mode": "RECONCILE" if receipt else "EXECUTE"}
            payload["admission_digest"] = canonical_digest(payload)
            permit_id = str(uuid4())
            self.aquila.store.connection.execute("INSERT INTO spike_action_permits VALUES (?, ?, 'ISSUED')",
                (permit_id, json.dumps(payload, sort_keys=True)))
            self._audit(view, scope, "SPIKE_ACTION_PERMIT_ISSUED", {"permit_id": permit_id,
                "admission_digest": payload["admission_digest"], "action_digest": digest})
            return permit_id

    def consume(self, permit_id, scope, arguments):
        """Called by the independent enforcer at admission, not a Strands hook."""
        digest = action_digest(arguments)
        with self._view(scope) as (view, mission):
            row = self.aquila.store.connection.execute(
                "SELECT * FROM spike_action_permits WHERE id=?", (permit_id,)).fetchone()
            if not row or row["status"] != "ISSUED":
                raise AuthorizationError("SPIKE_PERMIT_INVALID_OR_REPLAYED")
            payload = json.loads(row["payload"])
            admission_digest = payload.pop("admission_digest")
            if (payload["scope"] != scope.payload() or payload["capability"] != CAPABILITY
                    or payload["action_digest"] != digest or canonical_digest(payload) != admission_digest
                    or payload["mission_version"] != mission.version
                    or payload["roe_revision"] != mission.roe.revision
                    or payload["policy_version"] != view.authorization.policy.version
                    or datetime.fromisoformat(view.authorization.clock()) >= datetime.fromisoformat(payload["expires_at"])):
                raise AuthorizationError("SPIKE_PERMIT_CONTEXT_MISMATCH")
            self._dispatch_check(view, mission, scope, arguments)
            self.aquila.store.connection.execute("UPDATE spike_action_permits SET status='CONSUMED' WHERE id=?", (permit_id,))
            self._audit(view, scope, "SPIKE_ACTION_DISPATCH_ADMITTED", {"permit_id": permit_id,
                "admission_digest": admission_digest, "action_digest": digest})
            return payload["mode"]

    def record_receipt(self, permit_id, scope, arguments, receipt_id):
        """Record an observed committed effect, not permission for a new one."""
        digest = action_digest(arguments)
        with self._view(scope) as (view, mission):
            row = self.aquila.store.connection.execute(
                "SELECT * FROM spike_action_permits WHERE id=?", (permit_id,)).fetchone()
            if (not row or row["status"] != "CONSUMED" or json.loads(row["payload"])["scope"] != scope.payload()
                    or json.loads(row["payload"])["action_digest"] != digest):
                raise AuthorizationError("SPIKE_RECEIPT_WITHOUT_ADMISSION")
            prior = self._receipt(scope)
            if prior:
                if prior["receipt_id"] != receipt_id or prior["action_digest"] != digest:
                    raise AuthorizationError("SPIKE_RECEIPT_MISMATCH")
                return
            self.aquila.store.connection.execute("INSERT INTO spike_action_receipts VALUES (?, ?, ?, ?)",
                (scope.logical_operation_id, scope.mission_id, digest, receipt_id))
            for approval in view.kernel.approvals.values():
                if approval.action.id == scope.logical_operation_id and approval.status == "APPROVED":
                    approval.status = "CONSUMED"
            self._audit(view, scope, "SPIKE_EXTERNAL_EFFECT_RECORDED", {"permit_id": permit_id,
                "receipt_id": receipt_id, "action_digest": digest})

    @staticmethod
    def _audit(view, scope, event_type, data):
        view.kernel.record_spike_action_fact(mission_id=scope.mission_id, actor=scope.workload,
            correlation_id=scope.correlation_id, event_type=event_type, result="SUCCESS",
            data={"agent_id": scope.agent_id, "work_item_id": scope.work_item_id,
                  "attempt_id": scope.attempt_id, "cognition_execution_id": scope.execution_id,
                  "logical_operation_id": scope.logical_operation_id, **data})
