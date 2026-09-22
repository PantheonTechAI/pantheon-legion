"""Regression for interleaving a Mission mutation with fresh inference authority."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
import unittest
from uuid import uuid4

from aquila_api import PersistentAquilaService
from aquila_api.runtime_authority import InProcessAquilaCognitionAuthority
from legion_cognition.authorized import CognitionInvocationContext, CognitionInvocationFacts, now
from legion_cognition.capability import CognitionError, CognitionSelection
from legion_kernel import Principal, PrincipalType, RoeLevel


class CognitionAuthorityPersistenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        connection = sqlite3.connect(str(Path(directory.name) / "authority.sqlite3"), check_same_thread=False)
        self.addCleanup(connection.close)
        self.service = PersistentAquilaService(connection)
        self.owner = Principal(PrincipalType.HUMAN, "owner", frozenset({"MISSION_OWNER", "OPERATOR"}))
        self.worker = Principal(PrincipalType.WORKLOAD, "scout")
        self.mission_id = self.service.create_mission(actor=self.owner, body={
            "organization_id": str(uuid4()), "workspace_id": str(uuid4()),
            "title": "Persistence race", "objective": "Preserve authorized Mission changes."}).body["id"]
        grant = self.service.issue_delegation(issuer=self.owner, subject=self.worker, mission_id=self.mission_id,
            allowed_operations=frozenset({"INVOKE_COGNITION"}), roe_ceiling=RoeLevel.OBSERVE,
            expires_at="2099-01-01T00:00:00Z")
        self.context = CognitionInvocationContext(self.worker, grant, self.mission_id,
            *(str(uuid4()) for _ in range(5)))
        self.facts = CognitionInvocationFacts("0" * 64, CognitionSelection("a", "o", "p", "e", "n"),
                                            "m", 1, 1, "1" * 64, recorded_at=now())

    def test_inference_authorization_cannot_overwrite_inflight_mission_mutation(self):
        mutated, release, requested = Event(), Event(), Event()
        original = self.service.kernel.submit_command

        def paused_mutation(**kwargs):
            result = original(**kwargs)
            mutated.set()
            if not release.wait(5):
                raise TimeoutError("test release not received")
            return result

        self.service.kernel.submit_command = paused_mutation

        def mutation():
            return self.service.submit_command(actor=self.owner, mission_id=self.mission_id,
                body={"expected_version": 1, "command_type": "START", "payload": {}, "idempotency_key": "start-race"})

        def cognition():
            requested.set()
            return self.service.authorize_cognition(context=self.context, facts=self.facts)

        with ThreadPoolExecutor(max_workers=2) as pool:
            change = pool.submit(mutation)
            try:
                self.assertTrue(mutated.wait(5))
                authority = pool.submit(cognition)
                self.assertTrue(requested.wait(5))
                with self.assertRaises(FutureTimeout):
                    authority.result(timeout=0.05)
            finally:
                release.set()
            self.assertEqual(change.result(timeout=5).status_code, 200)
            self.assertEqual(authority.result(timeout=5).status_code, 200)
        self.assertEqual(self.service.store.get_mission(self.mission_id).version, 2)
        self.assertEqual(self.service.kernel.get_mission(self.mission_id).version, 2)
        persisted = self.service.store.get_audit(self.mission_id)
        self.assertEqual(persisted, self.service.kernel.audit[self.mission_id])
        self.assertTrue(any(event.event_type == "COGNITION_AUTHORIZATION_EVALUATED" for event in persisted))

    def test_expired_grant_and_terminal_mission_deny_inference(self):
        adapter = InProcessAquilaCognitionAuthority(self.service)
        self.service.authorization.clock = lambda: "2100-01-01T00:00:00Z"
        with self.assertRaisesRegex(CognitionError, "AUTHORITY_DENIED"):
            adapter.authorize(self.context, self.facts)
        self.service.authorization.clock = now
        response = self.service.cancel_mission(actor=self.owner, mission_id=self.mission_id,
            body={"expected_version": 1, "idempotency_key": "cancel-mission"})
        self.assertEqual(response.status_code, 200)
        with self.assertRaisesRegex(CognitionError, "AUTHORITY_DENIED"):
            adapter.authorize(self.context, self.facts)
        reasons = [event.data.get("reason") for event in self.service.store.get_audit(self.mission_id)]
        self.assertIn("DELEGATION_EXPIRED", reasons)
        self.assertIn("MISSION_TERMINAL", reasons)

    def test_legacy_knowledge_audit_survives_concurrent_cognition_authorization(self):
        grant = self.service.issue_delegation(issuer=self.owner, subject=self.worker, mission_id=self.mission_id,
            allowed_operations=frozenset({"READ_KNOWLEDGE"}), roe_ceiling=RoeLevel.OBSERVE,
            expires_at="2099-01-01T00:00:00Z")
        retrieving, release, requested = Event(), Event(), Event()

        class PausedReader:
            def retrieve(self, **kwargs):
                retrieving.set()
                if not release.wait(5):
                    raise TimeoutError("test release not received")
                return ()

        def cognition():
            requested.set()
            return self.service.authorize_cognition(context=self.context, facts=self.facts)

        with ThreadPoolExecutor(max_workers=2) as pool:
            read = pool.submit(self.service.retrieve_knowledge, mission_id=self.mission_id,
                worker=self.worker, delegation_id=grant, tabula=PausedReader(), query="bounded evidence")
            try:
                self.assertTrue(retrieving.wait(5))
                authority = pool.submit(cognition)
                self.assertTrue(requested.wait(5))
                with self.assertRaises(FutureTimeout):
                    authority.result(timeout=0.05)
            finally:
                release.set()
            self.assertEqual(read.result(timeout=5), ())
            self.assertEqual(authority.result(timeout=5).status_code, 200)
        persisted = self.service.store.get_audit(self.mission_id)
        self.assertEqual(persisted, self.service.kernel.audit[self.mission_id])
        reads = [event for event in persisted if event.event_type == "DELEGATION_EVALUATED"
                 and event.data.get("operation") == "READ_KNOWLEDGE"]
        self.assertEqual(len(reads), 1)
        self.assertTrue(any(event.event_type == "COGNITION_AUTHORIZATION_EVALUATED" for event in persisted))

    def test_unknown_mission_has_distinct_safe_error(self):
        adapter = InProcessAquilaCognitionAuthority(self.service)
        with self.assertRaisesRegex(CognitionError, "MISSION_NOT_FOUND"):
            adapter.authorize(replace(self.context, mission_id=str(uuid4())), self.facts)
