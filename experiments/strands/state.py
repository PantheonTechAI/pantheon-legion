"""Bounded operational snapshots; the Runtime ledger selects trusted generations.

Only P2 may retain native synthetic messages. Workers receive private copies,
never this store. A checksum supplied by a worker is not accepted as a manifest.
"""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from uuid import UUID

from legion_cognition.capability import CognitionError, digest
from .protocol import _pairs, _constant


MAX_STORE_BYTES = 8 * 1024 * 1024
PROHIBITED = ("SECRET_SENTINEL_DO_NOT_RETAIN", "EXPLICIT_REASONING_SENTINEL_DO_NOT_RETAIN")
NATIVE_PATH = re.compile(r"session_operational/(?:session\.json|agents/agent_[a-z-]+/(?:agent\.json|messages/message_[0-9]+\.json)|multi_agents/multi_agent_[a-z-]+/(?:multi_agent\.json|state\.json))\Z")


def strict_load(value):
    return json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)


class OperationalStore:
    def __init__(self, root, *, synthetic=False):
        candidate = Path(root)
        if candidate.is_symlink():
            raise ValueError("SPIKE_PRIVATE_STATE_ROOT_REQUIRED")
        self.root = candidate.resolve()
        self.synthetic = synthetic
        if not self.root.is_dir() or self.root.is_symlink():
            raise ValueError("SPIKE_PRIVATE_STATE_ROOT_REQUIRED")
        self._owner()
        os.chmod(self.root, 0o700)

    def _owner(self):
        marker = self.root / ".legion-strands-store.json"
        if not marker.exists():
            if any(self.root.iterdir()):
                raise ValueError("SPIKE_STATE_ROOT_NOT_EMPTY")
            owner = {"schema": 1, "purpose": "legion-strands-spike", "uid": os.getuid(),
                     "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()}
            descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "w") as output:
                json.dump(owner, output)
        if marker.is_symlink() or marker.stat().st_size > 1024:
            raise ValueError("SPIKE_STORE_OWNERSHIP_REFUSED")
        owner = strict_load(marker.read_text())
        if (set(owner) != {"schema", "purpose", "uid", "expires_at"} or owner["schema"] != 1
                or owner["purpose"] != "legion-strands-spike" or owner["uid"] != os.getuid()):
            raise ValueError("SPIKE_STORE_OWNERSHIP_REFUSED")
        return owner

    def _current(self):
        if datetime.now(timezone.utc) >= datetime.fromisoformat(self._owner()["expires_at"]):
            raise CognitionError("SPIKE_OPERATIONAL_STORE_EXPIRED")

    def scope(self, session, config):
        reader = session.runtime.evidence_reader
        binding = reader.binding
        return {"schema": 1, "sdk": "1.56.0", "config_digest": digest(config),
                "mission_id": session.work.mission_id, "agent_id": session.scout.agent_id,
                "work_item_id": session.work.work_item_id, "assignment_id": session.assignment.assignment_id,
                "binding_id": session.binding.binding_id, "grant_id": session.binding.grant_id,
                "knowledge_scope": asdict(binding),
                "evidence_identity": sorted([[item.record_id, item.revision] for item in session.evidence])}

    def _path(self, session):
        # Runtime constructed and validated this UUID; no path is supplied by a worker.
        work_id = session.work.work_item_id
        if str(UUID(work_id)) != work_id:
            raise CognitionError("SPIKE_STATE_SCOPE_REFUSED")
        path = self.root / work_id
        if path.is_symlink():
            raise CognitionError("SPIKE_STATE_SCOPE_REFUSED")
        return path

    def _latest(self, session):
        values = [op for op in session.runtime.repository.list_spike_operations(session.work.work_item_id)
                  if op.kind == "SESSION" and op.status == "SUCCESS"]
        return max(values, key=lambda op: op.ordinal) if values else None

    def restore(self, session, directory, config):
        self._current()
        if config["persistence"] == "P2" and not self.synthetic:
            raise CognitionError("SPIKE_NATIVE_REQUIRES_SYNTHETIC_DATA")
        prior = self._latest(session)
        if prior is None:
            return False
        path = self._path(session) / (str(prior.ordinal) + ".json")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_STORE_BYTES:
            raise CognitionError("SPIKE_SNAPSHOT_REFUSED")
        try:
            payload = strict_load(path.read_text())
            if (set(payload) != {"scope", "generation", "source_attempt_id", "source_execution_id", "state"}
                    or payload["scope"] != self.scope(session, config)
                    or payload["generation"] != prior.ordinal
                    or payload["source_attempt_id"] != prior.attempt_id
                    or payload["source_execution_id"] != prior.execution_id
                    or digest(payload) != prior.facts["snapshot_digest"]):
                raise ValueError
            if config["persistence"] == "P1":
                if payload["state"] != {"version": 1, "progress": "replacement-ready"}:
                    raise ValueError
                return True  # Safe hint only; deliberately regenerate all context.
            state = payload["state"]
            if not isinstance(state, dict) or not state:
                raise ValueError
            for name, value in state.items():
                self._validate_native(name, value)
            target = Path(directory) / "native"
            target.mkdir(mode=0o700)
            for name, value in state.items():
                destination = target.joinpath(*PurePosixPath(name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                destination.write_text(json.dumps(value, ensure_ascii=False))
                destination.chmod(0o600)
            return True
        except (ValueError, TypeError, KeyError, OSError):
            raise CognitionError("SPIKE_SNAPSHOT_REFUSED") from None

    @staticmethod
    def _validate_native(name, value):
        if not isinstance(name, str) or not NATIVE_PATH.fullmatch(name) or not isinstance(value, dict):
            raise ValueError("SPIKE_NATIVE_SCHEMA_REFUSED")
        serialized = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if any(sentinel in serialized for sentinel in PROHIBITED) or '"reasoningContent"' in serialized:
            raise ValueError("SPIKE_PROHIBITED_CONTENT")

    def capture(self, session, directory, config):
        self._current()
        session.guard()
        state = {"version": 1, "progress": "replacement-ready"}
        if config["persistence"] == "P2":
            if not self.synthetic:
                raise CognitionError("SPIKE_NATIVE_REQUIRES_SYNTHETIC_DATA")
            state = {}
            base = Path(directory) / "native"
            if base.is_symlink():
                raise CognitionError("SPIKE_SNAPSHOT_SYMLINK")
            size = 0
            for path in base.rglob("*"):
                if path.is_symlink():
                    raise CognitionError("SPIKE_SNAPSHOT_SYMLINK")
                if not path.is_file():
                    continue
                size += path.stat().st_size
                if size > MAX_STORE_BYTES:
                    raise CognitionError("SPIKE_SNAPSHOT_TOO_LARGE")
                name = path.relative_to(base).as_posix()
                value = strict_load(path.read_text())
                self._validate_native(name, value)
                state[name] = value
            if not state:
                raise CognitionError("SPIKE_NATIVE_SNAPSHOT_MISSING")
        prior = self._latest(session)
        generation = prior.ordinal + 1 if prior else 1
        payload = {"scope": self.scope(session, config), "generation": generation,
                   "source_attempt_id": session.attempt.attempt_id, "source_execution_id": session.execution_id,
                   "state": state}
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        directory = self._path(session)
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_symlink() or sum(path.stat().st_size for path in directory.iterdir()) + len(encoded) > MAX_STORE_BYTES:
            raise CognitionError("SPIKE_SNAPSHOT_TOO_LARGE")
        checksum = digest(payload)
        operation = session.reserve("SESSION", checksum,
            {"snapshot_digest": checksum, "snapshot_generation": generation})
        if operation.ordinal != generation:
            raise CognitionError("SPIKE_SNAPSHOT_GENERATION_CONFLICT")
        path = directory / (str(generation) + ".json")
        # Exclusive generation creation: a stale/duplicate producer cannot overwrite it.
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        session.complete(operation, facts=operation.facts, status="SUCCESS")

    def delete(self, session):
        self._owner()
        path = self._path(session)
        if path.parent != self.root or path.is_symlink():
            raise CognitionError("SPIKE_CLEANUP_SCOPE_REFUSED")
        if path.exists():
            shutil.rmtree(path)

    def expire(self):
        """Explicit cleanup of expired, exactly identified owned trial directories."""
        if datetime.now(timezone.utc) < datetime.fromisoformat(self._owner()["expires_at"]):
            raise CognitionError("SPIKE_OPERATIONAL_STORE_NOT_EXPIRED")
        targets = []
        for path in self.root.iterdir():
            if path.name == ".legion-strands-store.json":
                continue
            if path.is_symlink() or not path.is_dir() or str(UUID(path.name)) != path.name:
                raise CognitionError("SPIKE_CLEANUP_SCOPE_REFUSED")
            targets.append(path)
        for path in targets:
            shutil.rmtree(path)
        return len(targets)
