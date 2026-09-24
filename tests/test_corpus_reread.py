import copy
from hashlib import sha256
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from legion_tabula.corpus import CorpusReadError, CorpusReference, ScopeBinding, TabulaCorpusClient
from legion_tabula.mcp import McpHttpTransport, McpResponse, McpTransportError
from tests import test_tabula_corpus_client as fixtures
BINDING_ID, CORRELATION_ID = fixtures.BINDING_ID, fixtures.CORRELATION_ID


class CorpusRereadTests(unittest.TestCase):
    def setUp(self):
        self.binding = ScopeBinding(BINDING_ID, "1.0.0")
        self.calls = []
        self.tokens = []
        self.mutate = lambda body: None
        body = fixtures.TabulaCorpusClientTests._success({"request_id": CORRELATION_ID,
                                               "correlation_id": CORRELATION_ID,
                                               "binding": self.binding.payload()}).body
        self.record = body["results"][0]
        raw = self.record["content"].encode()
        self.ref = CorpusReference(self.record["record_id"], self.record["revision"],
                                   self.record["canonical_uri"], len(raw), sha256(raw).hexdigest())

    def transport(self, token, call):
        self.tokens.append(token())
        self.calls.append(call)
        body = fixtures.TabulaCorpusClientTests._success(call["arguments"]).body
        self.mutate(body)
        return McpResponse(200, body)

    def read(self, transport=None, references=None):
        return TabulaCorpusClient(transport or self.transport).reread(
            token=lambda: f"token-{len(self.calls)}", binding=self.binding,
            references=references or (self.ref,), correlation_id=CORRELATION_ID)

    def test_exact_content_with_query_free_metadata_request(self):
        result = self.read()
        self.assertEqual(result.records[0].content, self.record["content"])
        call = self.calls[0]
        self.assertEqual(call["name"], "legion_reread_corpus")
        self.assertEqual(call["arguments"]["references"], [self.ref.payload()])
        self.assertNotIn("query", call["arguments"])
        self.assertNotIn("canonical_uri", call["arguments"]["references"][0])

    def test_rejects_partial_duplicate_extra_and_substituted_evidence(self):
        mutations = [
            lambda b: b["results"].clear(),
            lambda b: b["results"].append(copy.deepcopy(b["results"][0])),
        ] + [
            (lambda b, k=k, v=v: b["results"][0].update({k: v}))
            for k, v in (("record_id", "replacement"), ("revision", "r8"),
                         ("canonical_uri", "urn:other"), ("content", "changed"))]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.mutate = mutate
                with self.assertRaisesRegex(CorpusReadError, "TABULA_PROTOCOL_ERROR"):
                    self.read()

    def test_only_service_unavailable_retries_with_new_request_and_token(self):
        for code in ("AUTHORIZATION_DENIED", "DEADLINE_EXCEEDED", "SERVICE_UNAVAILABLE"):
            self.calls.clear()
            self.tokens.clear()
            def transport(token, call):
                reply = self.transport(token, call)
                if len(self.calls) == 1:
                    body = {k: reply.body[k] for k in ("schema_version", "request_id", "correlation_id", "tabula_audit_correlation_id")}
                    body.update(code=code, retryable=code == "SERVICE_UNAVAILABLE")
                    if code == "SERVICE_UNAVAILABLE":
                        body["retry_after_ms"] = 10
                    return McpResponse(200, body)
                return reply
            if code == "SERVICE_UNAVAILABLE":
                self.read(transport)
                self.assertEqual(len(set(self.tokens)), 2)
                self.assertNotEqual(self.calls[0]["arguments"]["request_id"], self.calls[1]["arguments"]["request_id"])
            else:
                with self.assertRaisesRegex(CorpusReadError, code):
                    self.read(transport)
                self.assertEqual(len(self.calls), 1)

    def test_requires_bounded_real_transport_before_credentials_or_io(self):
        with self.assertRaisesRegex(ValueError, "UNBOUNDED"):
            self.read(McpHttpTransport("http://unreachable.test/mcp"))

    def test_count_byte_digest_and_duplicate_request_bounds(self):
        for count in (True, 0, 8193):
            with self.assertRaises(ValueError):
                CorpusReference("id", "r1", "urn:id", count, "0" * 64)
        with self.assertRaises(ValueError):
            self.read(references=(self.ref, self.ref))
        self.assertEqual(self.calls, [])


class BoundedMcpTests(unittest.TestCase):
    def test_success_and_http_error_bodies_are_bounded_before_decode_and_closed(self):
        class Response(io.BytesIO):
            status = 200
            headers = {}
            def __init__(self):
                super().__init__(b"x" * 100)
                self.read_sizes = []
            def read(self, size=-1):
                self.read_sizes.append(size)
                return super().read(size)
        for http_error in (False, True):
            response = Response()
            error = HTTPError("http://example.test", 500, "failure", {}, response)
            transport = McpHttpTransport("http://example.test", max_response_bytes=16)
            transport._session_id = "session"
            with patch("legion_tabula.mcp.urlopen", side_effect=error if http_error else None,
                       return_value=response), patch("legion_tabula.mcp._decode_body") as decode:
                with self.assertRaisesRegex(McpTransportError, "TABULA_PROTOCOL_ERROR"):
                    transport(lambda: "credential", {"name": "legion_reread_corpus"})
            self.assertEqual(response.read_sizes, [17])
            self.assertTrue(response.closed)
            decode.assert_not_called()
