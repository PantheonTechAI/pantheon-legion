"""Provider-neutral durable execution adapter and reference implementation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Protocol
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ExecutionState(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING = "WAITING"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class ExecutionRecord:
    execution_id: str
    mission_id: str
    command_id: str
    idempotency_key: str
    state: ExecutionState
    attempt: int
    input: dict[str, Any]
    created_at: str
    updated_at: str
    result: dict[str, Any] | None = None
    failure: str | None = None


class DurableExecutionAdapter(Protocol):
    """The provider-neutral lifecycle contract used by Aquila."""

    def start(
        self,
        *,
        mission_id: str,
        command_id: str,
        idempotency_key: str,
        input: dict[str, Any],
    ) -> ExecutionRecord: ...

    def query(self, execution_id: str) -> ExecutionRecord: ...

    def signal(self, execution_id: str, name: str, payload: dict[str, Any] | None = None) -> ExecutionRecord: ...

    def cancel(self, execution_id: str, reason: str) -> ExecutionRecord: ...

    def recover(self, execution_id: str) -> ExecutionRecord: ...

    def complete(self, execution_id: str, result: dict[str, Any]) -> ExecutionRecord: ...

    def fail(self, execution_id: str, reason: str) -> ExecutionRecord: ...


class InMemoryDurableExecutionAdapter:
    """Deterministic reference provider for contract and failure-injection tests."""

    def __init__(self, snapshot: dict[str, Any] | None = None) -> None:
        self.records: dict[str, ExecutionRecord] = {}
        self.by_idempotency: dict[tuple[str, str], str] = {}
        if snapshot:
            self._restore(snapshot)

    def start(
        self,
        *,
        mission_id: str,
        command_id: str,
        idempotency_key: str,
        input: dict[str, Any],
    ) -> ExecutionRecord:
        key = (mission_id, idempotency_key)
        existing_id = self.by_idempotency.get(key)
        if existing_id:
            existing = self.records[existing_id]
            if existing.command_id != command_id or existing.input != input:
                raise ValueError("EXECUTION_IDEMPOTENCY_KEY_REUSE")
            return deepcopy(existing)
        timestamp = _now()
        record = ExecutionRecord(
            execution_id=str(uuid4()),
            mission_id=mission_id,
            command_id=command_id,
            idempotency_key=idempotency_key,
            state=ExecutionState.RUNNING,
            attempt=1,
            input=deepcopy(input),
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.records[record.execution_id] = record
        self.by_idempotency[key] = record.execution_id
        return deepcopy(record)

    def query(self, execution_id: str) -> ExecutionRecord:
        return deepcopy(self._record(execution_id))

    def signal(
        self,
        execution_id: str,
        name: str,
        payload: dict[str, Any] | None = None,
    ) -> ExecutionRecord:
        record = self._record(execution_id)
        if record.state in {ExecutionState.CANCELLED, ExecutionState.COMPLETED}:
            raise ValueError("EXECUTION_TERMINAL")
        transitions = {
            "PAUSE": ExecutionState.PAUSED,
            "RESUME": ExecutionState.RUNNING,
            "WAIT": ExecutionState.WAITING,
        }
        if name not in transitions:
            raise ValueError("UNKNOWN_EXECUTION_SIGNAL")
        record.state = transitions[name]
        record.updated_at = _now()
        if payload:
            record.input.setdefault("signals", []).append({"name": name, "payload": deepcopy(payload)})
        return deepcopy(record)

    def cancel(self, execution_id: str, reason: str) -> ExecutionRecord:
        record = self._record(execution_id)
        if record.state in {ExecutionState.CANCELLED, ExecutionState.COMPLETED}:
            return deepcopy(record)
        record.state = ExecutionState.CANCELLED
        record.failure = reason
        record.updated_at = _now()
        return deepcopy(record)

    def recover(self, execution_id: str) -> ExecutionRecord:
        record = self._record(execution_id)
        if record.state in {ExecutionState.CANCELLED, ExecutionState.COMPLETED}:
            return deepcopy(record)
        record.attempt += 1
        record.state = ExecutionState.RUNNING
        record.updated_at = _now()
        return deepcopy(record)

    def complete(self, execution_id: str, result: dict[str, Any]) -> ExecutionRecord:
        record = self._record(execution_id)
        if record.state == ExecutionState.COMPLETED:
            return deepcopy(record)
        if record.state == ExecutionState.CANCELLED:
            raise ValueError("EXECUTION_CANCELLED")
        record.state = ExecutionState.COMPLETED
        record.result = deepcopy(result)
        record.updated_at = _now()
        return deepcopy(record)

    def fail(self, execution_id: str, reason: str) -> ExecutionRecord:
        record = self._record(execution_id)
        if record.state in {ExecutionState.CANCELLED, ExecutionState.COMPLETED}:
            raise ValueError("EXECUTION_TERMINAL")
        record.state = ExecutionState.FAILED
        record.failure = reason
        record.updated_at = _now()
        return deepcopy(record)

    def snapshot(self) -> dict[str, Any]:
        return {
            "records": [
                {
                    **asdict(record),
                    "state": record.state.value,
                }
                for record in self.records.values()
            ],
            "by_idempotency": [
                {"mission_id": mission_id, "key": key, "execution_id": execution_id}
                for (mission_id, key), execution_id in self.by_idempotency.items()
            ],
        }

    def _restore(self, snapshot: dict[str, Any]) -> None:
        for raw in snapshot.get("records", []):
            raw = dict(raw)
            raw["state"] = ExecutionState(raw["state"])
            self.records[raw["execution_id"]] = ExecutionRecord(**raw)
        for item in snapshot.get("by_idempotency", []):
            self.by_idempotency[(item["mission_id"], item["key"])] = item["execution_id"]

    def _record(self, execution_id: str) -> ExecutionRecord:
        try:
            return self.records[execution_id]
        except KeyError as exc:
            raise KeyError(f"Unknown execution {execution_id}") from exc
