from dataclasses import asdict, replace
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config

from aquila_api.runtime_authority import InProcessAquilaCognitionAuthority
from legion_cognition.authorized import AuthorizedCognitionInvoker
from legion_cognition.capability import CognitionError, CognitionRouter
from legion_cognition.openai_compatible import OpenAICompatibleTransport, TransportPolicy
from legion_runtime import AttemptStage, AttemptStatus, PersistentAgentRuntime, RepositoryMissionOrganizationReadModel, RuntimeOperationError, WorkKind
from tests.acceptance.grounded_scout_runner import GroundedScoutAcceptanceRunner, CORRELATION
from tests.cognition_http import REASONING_SENTINEL, final_response, inference_server, tool_response
from tests.runtime_postgres import new_runtime_store, reset_runtime_database, runtime_test_database_url
from tests.test_cognition_capability import catalog


def development_transport(**kwargs):
    with unittest.TestCase().assertWarns(RuntimeWarning):
        return OpenAICompatibleTransport(policy=TransportPolicy(mode="live_acceptance", acknowledge_cleartext=True,
                                         acknowledge_unauthenticated=True), **kwargs)


def composition(directory, origin):
    runner = GroundedScoutAcceptanceRunner()
    state = runner._composition(directory)
    resources, offerings = catalog(origin)
    transport = development_transport()
    router = CognitionRouter(resources, offerings, transport)
    authority = InProcessAquilaCognitionAuthority(state["aquila"])
    invoker = AuthorizedCognitionInvoker(router, transport, authority)
    runtime = state["runtime"]
    runtime.cognition_invoker = invoker
    grant = runner._grant(state["aquila"], state["mission_id"], state["scout_workload"],
                          {"READ_MISSION", "READ_KNOWLEDGE", "INVOKE_COGNITION"})
    binding = runtime.resume_assignment(assignment_id=state["scout_assignment"].assignment_id,
        workload=state["scout_workload"], delegation_id=grant, correlation_id=CORRELATION,
        idempotency_key="resume-cognitive-scout").binding
    state.update(scout_binding=binding, scout_grant=grant, invoker=invoker, router=router,
                 inference_transport=transport, inference_authority=authority)
    return runner, state


def delegate(state):
    return state["runtime"].delegate_work(centurion_binding_id=state["centurion_binding"].binding_id,
        workload=state["centurion_workload"], scout_assignment_id=state["scout_assignment"].assignment_id,
        objective="Find architecture evidence", required_capabilities=("read_only_analysis", "model_reasoning", "tabula_corpus_read"),
        correlation_id=CORRELATION, idempotency_key="delegate-cognitive-work", work_kind=WorkKind.TOOL_ASSISTED_CORPUS_ANALYSIS)


class AuthorizedCognitionTests(unittest.TestCase):
    def setUp(self):
        reset_runtime_database()

    def state(self, responses=None):
        from contextlib import ExitStack
        stack = ExitStack()
        self.addCleanup(stack.close)
        peer = stack.enter_context(inference_server(responses))
        directory = stack.enter_context(tempfile.TemporaryDirectory())
        runner, state = composition(directory, peer.origin)
        stack.callback(runner._close, state)
        return runner, state, peer

    def test_complete_http_loop_has_fresh_authority_safe_provenance_and_matching_tool_result(self):
        runner, state, peer = self.state()
        work = delegate(state)
        attempt, result = runner._claim_and_execute(state, work)
        chats = [request for path, request, headers in peer.requests if request is not None]
        self.assertEqual(len(chats), 2)
        self.assertFalse(chats[0]["parallel_tool_calls"])
        self.assertEqual(chats[1]["messages"][-1]["tool_call_id"], "call-one")
        self.assertEqual(chats[1]["messages"][-2]["tool_calls"][0]["id"], "call-one")
        self.assertNotIn("tools", chats[1])
        self.assertEqual(len(result.evidence_references), 1)
        turns = state["runtime"].repository.list_cognition_turns(work.work_item_id)
        self.assertEqual([turn["status"] for turn in turns], ["SUCCESS", "SUCCESS"])
        self.assertEqual(len({turn["decision_id"] for turn in turns}), 2)
        self.assertTrue(all(turn["catalog_revision"] == "catalog-a" for turn in turns))
        audit = state["aquila"].store.get_audit(state["mission_id"])
        operations = [event.event_type for event in audit]
        self.assertEqual(operations.count("COGNITION_AUTHORIZATION_EVALUATED"), 2)
        self.assertEqual(operations.count("COGNITION_INVOCATION_COMPLETED"), 2)
        self.assertEqual(operations.count("EXTERNAL_READ_AUTHORIZATION_EVALUATED"), 3)
        projection = RepositoryMissionOrganizationReadModel(state["runtime"].repository).snapshot(
            organization_id=state["scout"].organization_id, workspace_id=state["scout"].workspace_id,
            mission_id=state["mission_id"])
        safe = repr(turns) + repr(projection) + repr(audit) + repr(state["runtime"].list_events(state["scout"].agent_id))
        for sentinel in (REASONING_SENTINEL, "non-durable raw acceptance evidence", "Authorization", "Bearer "):
            self.assertNotIn(sentinel, safe)

    def test_retry_uses_new_decision_and_stale_revision_prevents_retry_transport(self):
        runner, state, peer = self.state([(503, b"PRIVATE_PROVIDER_ERROR"), tool_response(), final_response()])
        work = delegate(state)
        runner._claim_and_execute(state, work)
        turns = state["runtime"].repository.list_cognition_turns(work.work_item_id)
        self.assertEqual(len(turns), 3)
        self.assertEqual(len({turn["decision_id"] for turn in turns}), 3)
        self.assertEqual(turns[0]["status"], "FAILED")

    def test_invalid_initial_calls_fail_before_knowledge(self):
        invalid = [final_response(), tool_response(name="shell"), tool_response('{"query":"x","binding":"evil"}'),
                   tool_response('{"query":'), tool_response('{"query":"a","query":"b"}'),
                   tool_response(json.dumps({"query": "x" * 2001}))]
        multiple = tool_response()
        multiple["choices"][0]["message"]["tool_calls"].append(
            {"id": "call-two", "type": "function", "function": {"name": "tabula_search", "arguments": '{"query":"x"}'}})
        invalid.append(multiple)
        for response in invalid:
            with self.subTest(response=response["id"]):
                reset_runtime_database()
                runner, state, peer = self.state([response])
                work = delegate(state)
                with self.assertRaises(RuntimeOperationError):
                    runner._claim_and_execute(state, work)
                self.assertEqual(state["transport"].protected_calls, 0)
                self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))

    def test_missing_cognition_grant_and_revocation_prevent_chat(self):
        runner, state, peer = self.state()
        aquila = state["aquila"]
        aquila.revoke_delegation(actor=runner.owner, mission_id=state["mission_id"],
                                delegation_id=state["scout_grant"], reason="test revocation")
        work = delegate(state)
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, work)
        self.assertFalse(any(request is not None for _, request, _ in peer.requests))
        self.assertEqual(state["transport"].protected_calls, 0)

    def test_knowledge_revocation_after_tool_response_prevents_continuation(self):
        runner, state, peer = self.state()
        original = state["inference_transport"].chat

        def revoke_after_chat(*args, **kwargs):
            response = original(*args, **kwargs)
            state["aquila"].revoke_delegation(actor=runner.owner, mission_id=state["mission_id"],
                delegation_id=state["scout_grant"], reason="revoke knowledge boundary")
            return response

        state["inference_transport"].chat = revoke_after_chat
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, delegate(state))
        self.assertEqual(sum(request is not None for _, request, _ in peer.requests), 1)
        self.assertEqual(state["transport"].protected_calls, 0)

    def test_post_audit_failure_leaves_external_stage_ambiguous(self):
        runner, state, peer = self.state()
        work = delegate(state)
        with patch.object(state["aquila"], "record_cognition_outcome", side_effect=OSError("PRIVATE_ERROR")):
            with self.assertRaisesRegex(RuntimeOperationError, "COGNITION_AUDIT_UNAVAILABLE"):
                runner._claim_and_execute(state, work)
        attempt = state["runtime"].repository.get_latest_work_attempt(work.work_item_id)
        self.assertEqual(attempt.status, AttemptStatus.RUNNING)
        self.assertEqual(attempt.attempt_stage, AttemptStage.COGNITION_INITIAL)
        self.assertEqual(state["transport"].protected_calls, 0)
        self.assertEqual(state["runtime"].repository.list_cognition_turns(work.work_item_id)[0]["status"], "PREPARED")

    def test_migration_refuses_cognition_data_downgrade(self):
        runner, state, peer = self.state()
        work = delegate(state)
        runner._claim_and_execute(state, work)
        with patch.dict(os.environ, {"LEGION_RUNTIME_DATABASE_URL": runtime_test_database_url()}):
            with self.assertRaisesRegex(RuntimeError, "cannot downgrade"):
                command.downgrade(Config("legion_runtime/alembic.ini"), "0003")
        self.assertEqual(len(state["runtime"].repository.list_cognition_turns(work.work_item_id)), 2)

    def test_every_ambiguous_stage_restarts_with_fresh_authority_and_one_result(self):
        class Crash(BaseException):
            pass

        for stage in (AttemptStage.COGNITION_SELECTION, AttemptStage.COGNITION_INITIAL,
                      AttemptStage.TOOL_REQUESTED, AttemptStage.EVIDENCE_RETRIEVAL, AttemptStage.COGNITION_CONTINUATION):
            with self.subTest(stage=stage):
                reset_runtime_database()
                runner, state, peer = self.state()
                runtime = state["runtime"]
                work = delegate(state)
                original_event = runtime._event

                def event_hook(**kwargs):
                    original_event(**kwargs)

                # Crash after the transaction containing the stage has committed.
                original_transaction = runtime.repository.transaction
                from contextlib import contextmanager
                crashed = False

                @contextmanager
                def crash_transaction(**kwargs):
                    nonlocal crashed
                    with original_transaction(**kwargs):
                        yield
                    if not crashed and runtime.repository._connection is None:
                        latest = runtime.repository.get_latest_work_attempt(work.work_item_id)
                        if latest and latest.attempt_stage == stage:
                            crashed = True
                            raise Crash()

                with patch.object(runtime.repository, "transaction", crash_transaction):
                    with self.assertRaises(Crash):
                        runner._claim_and_execute(state, work)
                old = runtime.repository.get_latest_work_attempt(work.work_item_id)
                prior_decisions = {row["decision_id"] for row in runtime.repository.list_cognition_turns(work.work_item_id)}
                runtime.close()
                state["runtime"] = PersistentAgentRuntime(new_runtime_store(), state["mission_authority"],
                    mission_context=state["mission_authority"], evidence_reader=state["evidence_reader"],
                    cognition_invoker=state["invoker"])
                runtime = state["runtime"]
                runtime.reconcile_work(work_item_id=work.work_item_id, scout_binding_id=state["scout_binding"].binding_id,
                    workload=state["scout_workload"], idempotency_key="recover-stage")
                peer.responses[:] = [tool_response(), final_response()]
                fresh, result = runner._claim_and_execute(state, work, suffix="fresh")
                self.assertNotEqual(fresh.attempt_id, old.attempt_id)
                self.assertEqual(runtime.repository.get_work_attempt(old.attempt_id).status, AttemptStatus.ABANDONED)
                self.assertEqual(runtime.get_work_result(work.work_item_id).result_id, result.result_id)
                new_decisions = {row["decision_id"] for row in runtime.repository.list_cognition_turns(work.work_item_id)
                                 if row["attempt_id"] == fresh.attempt_id}
                self.assertFalse(prior_decisions & new_decisions)

    def test_cancellation_after_each_chat_prevents_next_boundary_or_result(self):
        for cancel_turn in (1, 2):
            with self.subTest(turn=cancel_turn):
                reset_runtime_database()
                runner, state, peer = self.state()
                work = delegate(state)
                original = state["inference_transport"].chat
                count = 0

                def cancel_after_chat(*args, **kwargs):
                    nonlocal count
                    response = original(*args, **kwargs)
                    count += 1
                    if count == cancel_turn:
                        state["runtime"].cancel_work(work_item_id=work.work_item_id,
                            centurion_binding_id=state["centurion_binding"].binding_id,
                            workload=state["centurion_workload"], reason="cancel at inference boundary",
                            idempotency_key="cancel-inference")
                    return response

                state["inference_transport"].chat = cancel_after_chat
                with self.assertRaisesRegex(RuntimeOperationError, "WORK_CANCELLED"):
                    runner._claim_and_execute(state, work)
                self.assertEqual(count, cancel_turn)
                self.assertIsNone(state["runtime"].get_work_result(work.work_item_id))
                if cancel_turn == 1:
                    self.assertEqual(state["transport"].protected_calls, 0)

    def test_revision_change_after_ambiguous_attempt_keeps_original_tuple(self):
        runner, state, peer = self.state()
        work = delegate(state)
        with patch.object(state["aquila"], "record_cognition_outcome", side_effect=OSError("audit unavailable")):
            with self.assertRaises(RuntimeOperationError):
                runner._claim_and_execute(state, work)
        resources, offerings = catalog(peer.origin, revision="catalog-b")
        resources = replace(resources, nodes=(replace(resources.nodes[0], node_id="node-b"),),
                            endpoints=(replace(resources.endpoints[0], node_id="node-b"),))
        state["router"].update_catalog(resources, offerings)
        state["runtime"].reconcile_work(work_item_id=work.work_item_id, scout_binding_id=state["scout_binding"].binding_id,
            workload=state["scout_workload"], idempotency_key="recover-revision")
        peer.responses[:] = [tool_response(), final_response()]
        runner._claim_and_execute(state, work, suffix="revision-b")
        turns = state["runtime"].repository.list_cognition_turns(work.work_item_id)
        self.assertEqual([(turn["catalog_revision"], turn["node_id"]) for turn in turns],
                         [("catalog-a", "node-a"), ("catalog-b", "node-b"), ("catalog-b", "node-b")])
        self.assertEqual(state["runtime"].get_work_item(work.work_item_id).objective, work.objective)

    def test_retry_stops_when_catalog_changes_and_nonretryable_errors_do_not_retry(self):
        runner, state, peer = self.state([(503, b"PRIVATE_PROVIDER_ERROR"), tool_response()])
        original = state["inference_authority"].record_outcome

        def change_catalog(context, facts):
            original(context, facts)
            resources, offerings = catalog(peer.origin, revision="catalog-b")
            state["router"].update_catalog(resources, offerings)

        state["inference_authority"].record_outcome = change_catalog
        with self.assertRaisesRegex(RuntimeOperationError, "SELECTION_STALE"):
            runner._claim_and_execute(state, delegate(state))
        self.assertEqual(sum(request is not None for _, request, _ in peer.requests), 1)

    def test_praetorium_is_authorized_safe_and_failure_isolated(self):
        import io
        from praetorium import PraetoriumWSGIApp
        runner, state, peer = self.state()
        work = delegate(state)
        runner._claim_and_execute(state, work)

        class Auth:
            def authenticate(self, environ):
                return runner.owner

        read_model = RepositoryMissionOrganizationReadModel(state["runtime"].repository)
        app = PraetoriumWSGIApp(state["aquila"], Auth(), organization_id=state["scout"].organization_id,
            workspace_id=state["scout"].workspace_id, tabula_console_url="https://tabula.example", organization_read_model=read_model)
        captured = []
        environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/praetorium/missions/" + state["mission_id"],
                   "CONTENT_LENGTH": "0", "wsgi.input": io.BytesIO()}
        body = b"".join(app(environ, lambda status, headers: captured.append(status))).decode()
        self.assertTrue(captured[-1].startswith("200"))
        self.assertIn("Supporting evidence inputs", body)
        self.assertIn("catalog-a", body)
        self.assertNotIn(REASONING_SENTINEL, body)
        with patch.object(read_model, "snapshot", side_effect=OSError("PRIVATE_DB_ERROR")):
            body = b"".join(app(environ, lambda status, headers: captured.append(status))).decode()
        self.assertTrue(captured[-1].startswith("200"))
        self.assertIn("Organization status unavailable", body)
        self.assertNotIn("PRIVATE_DB_ERROR", body)

    def test_read_mission_grant_does_not_imply_cognition_permission(self):
        runner, state, peer = self.state()
        grant = runner._grant(state["aquila"], state["mission_id"], state["scout_workload"],
                              {"READ_MISSION", "READ_KNOWLEDGE"})
        state["scout_binding"] = state["runtime"].resume_assignment(
            assignment_id=state["scout_assignment"].assignment_id, workload=state["scout_workload"],
            delegation_id=grant, correlation_id=CORRELATION, idempotency_key="resume-without-cognition").binding
        with self.assertRaisesRegex(RuntimeOperationError, "COGNITION_AUTHORITY_DENIED"):
            runner._claim_and_execute(state, delegate(state))
        self.assertEqual(sum(request is not None for _, request, _ in peer.requests), 0)
        self.assertEqual(state["transport"].protected_calls, 0)

    def test_concurrent_workers_accept_one_result(self):
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        from aquila_api import PersistentAquilaService, InProcessAquilaAgentAuthority, InProcessAquilaKnowledgeAuthority
        from legion_tabula import TabulaCorpusClient
        from legion_tabula.runtime_adapter import FederatedCorpusEvidenceReader
        runner, state, peer = self.state()
        work = delegate(state)
        state["runtime"].claim_work(work_item_id=work.work_item_id,
            scout_binding_id=state["scout_binding"].binding_id, workload=state["scout_workload"], idempotency_key="claim-race")

        def execute(ordinal):
            aquila = PersistentAquilaService(str(Path(state["directory"]) / "aquila.sqlite3"))
            authority = InProcessAquilaAgentAuthority(aquila)
            reader = FederatedCorpusEvidenceReader(client=TabulaCorpusClient(state["transport"]),
                authority=InProcessAquilaKnowledgeAuthority(aquila, state["knowledge_authority"].credential_issuer),
                binding=state["evidence_reader"].binding)
            runtime = PersistentAgentRuntime(new_runtime_store(), authority, mission_context=authority, evidence_reader=reader,
                cognition_invoker=AuthorizedCognitionInvoker(state["router"], state["inference_transport"],
                    InProcessAquilaCognitionAuthority(aquila)))
            try:
                return runtime.execute_scout_work(work_item_id=work.work_item_id,
                    scout_binding_id=state["scout_binding"].binding_id, workload=state["scout_workload"],
                    idempotency_key="execute-race-" + str(ordinal)).result_id
            except RuntimeOperationError as error:
                self.assertIn(error.code, {"WORK_RECONCILIATION_REQUIRED", "WORK_NOT_CLAIMED"})
                return None
            finally:
                runtime.close()
                aquila.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(execute, (1, 2)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertIn(state["runtime"].get_work_result(work.work_item_id).result_id, results)
        self.assertEqual(sum(request is not None for _, request, _ in peer.requests), 2)

    def test_binding_replacement_after_tool_response_prevents_knowledge(self):
        runner, state, peer = self.state()
        original = state["inference_transport"].chat

        def replace_binding(*args, **kwargs):
            result = original(*args, **kwargs)
            state["runtime"].resume_assignment(assignment_id=state["scout_assignment"].assignment_id,
                workload=state["scout_workload"], delegation_id=state["scout_grant"], correlation_id=CORRELATION,
                idempotency_key="replace-binding-at-boundary")
            return result

        state["inference_transport"].chat = replace_binding
        with self.assertRaises(RuntimeOperationError):
            runner._claim_and_execute(state, delegate(state))
        self.assertEqual(state["transport"].protected_calls, 0)

    def test_transport_credentials_do_not_enter_safe_state(self):
        runner, state, peer = self.state()
        resources, offerings = catalog(peer.origin, revision="credentials-a")
        offerings = replace(offerings, providers=(replace(offerings.providers[0], credential_reference="provider-secret"),))
        state["router"].update_catalog(resources, offerings)
        state["inference_transport"].secret_supplier = lambda reference: "SECRET_PROVIDER_SENTINEL"
        work = delegate(state)
        runner._claim_and_execute(state, work)
        self.assertTrue(all(headers.get("Authorization") == "Bearer SECRET_PROVIDER_SENTINEL"
                            for _, _, headers in peer.requests))
        safe = repr(state["runtime"].repository.list_cognition_turns(work.work_item_id))
        safe += repr(state["aquila"].store.get_audit(state["mission_id"]))
        safe += repr(state["runtime"].list_events(state["scout"].agent_id))
        self.assertNotIn("SECRET_PROVIDER_SENTINEL", safe)

    def test_actual_http_timeout_retries_with_fresh_authority(self):
        runner, state, peer = self.state([tool_response(), tool_response(), final_response()])
        peer.delays = [0.2, 0, 0]
        state["inference_transport"].policy = replace(state["inference_transport"].policy, timeout_seconds=0.05)
        work = delegate(state)
        runner._claim_and_execute(state, work)
        turns = state["runtime"].repository.list_cognition_turns(work.work_item_id)
        self.assertEqual(len(turns), 3)
        self.assertEqual(turns[0]["error_code"], "COGNITION_TRANSPORT_UNAVAILABLE")
        self.assertEqual(len({turn["decision_id"] for turn in turns}), 3)

    def test_nonretryable_provider_failures_never_reach_knowledge(self):
        for response in ((400, b"PRIVATE_BAD_REQUEST"), (200, b"malformed PRIVATE_BODY"), (200, b"x" * 131073)):
            with self.subTest(status=response[0]):
                reset_runtime_database()
                runner, state, peer = self.state([response])
                with self.assertRaises(RuntimeOperationError) as error:
                    runner._claim_and_execute(state, delegate(state))
                self.assertNotIn("PRIVATE", str(error.exception))
                self.assertEqual(sum(request is not None for _, request, _ in peer.requests), 1)
                self.assertEqual(state["transport"].protected_calls, 0)

    def test_fresh_cognition_authority_reads_cross_instance_revocation(self):
        from pathlib import Path
        from aquila_api import PersistentAquilaService
        runner, state, peer = self.state()
        original = state["inference_authority"].authorize

        def revoke_elsewhere(context, facts):
            other = PersistentAquilaService(str(Path(state["directory"]) / "aquila.sqlite3"))
            try:
                other.revoke_delegation(actor=runner.owner, mission_id=state["mission_id"],
                    delegation_id=state["scout_grant"], reason="separate process authority change")
            finally:
                other.close()
            return original(context, facts)

        state["inference_authority"].authorize = revoke_elsewhere
        with self.assertRaisesRegex(RuntimeOperationError, "COGNITION_AUTHORITY_DENIED"):
            runner._claim_and_execute(state, delegate(state))
        self.assertEqual(sum(request is not None for _, request, _ in peer.requests), 0)


class ProviderTransportTests(unittest.TestCase):
    def test_explicit_reasoning_discard_and_strict_final_tool_parsing(self):
        for response in (tool_response(), final_response()):
            result = OpenAICompatibleTransport.parse(json.dumps(response).encode())
            self.assertNotIn(REASONING_SENTINEL, repr(result))
        for content in ("", "a" * 8193, "é" * 4097):
            with self.assertRaisesRegex(CognitionError, "RESPONSE_INVALID"):
                OpenAICompatibleTransport.parse(json.dumps(final_response(content)).encode())
        mixed = tool_response()
        mixed["choices"][0]["message"]["content"] = "answer"
        with self.assertRaises(CognitionError):
            OpenAICompatibleTransport.parse(json.dumps(mixed).encode())

    def test_production_and_development_security_are_fail_closed(self):
        resources, offerings = catalog("http://localhost:8000")
        production = OpenAICompatibleTransport()
        with self.assertRaisesRegex(CognitionError, "PRODUCTION_SECURITY_REQUIRED"):
            production.validate_configuration(resources.endpoints[0], offerings.providers[0])
        for first, second in ((False, False), (True, False), (False, True)):
            with self.assertRaises(CognitionError):
                OpenAICompatibleTransport(policy=TransportPolicy(mode="live_acceptance",
                    acknowledge_cleartext=first, acknowledge_unauthenticated=second))

    def test_redirect_error_body_and_secret_supplier_failures_are_redacted(self):
        with inference_server([(302, b"PRIVATE_ERROR")]) as peer:
            resources, offerings = catalog(peer.origin)
            transport = development_transport()
            with self.assertRaises(CognitionError) as error:
                transport.chat(resources.endpoints[0], offerings.providers[0], offerings.offerings[0], [])
            self.assertNotIn("PRIVATE_ERROR", repr(error.exception))
            self.assertEqual(len(peer.requests), 1)
            provider = replace(offerings.providers[0], credential_reference="secret-reference")
            with self.assertRaisesRegex(CognitionError, "CREDENTIAL_UNAVAILABLE"):
                transport.chat(resources.endpoints[0], provider, offerings.offerings[0], [])
            self.assertEqual(len(peer.requests), 1)
