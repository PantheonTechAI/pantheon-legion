import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from legion_tabula.mcp import McpHttpTransport, McpTransportError


class McpHttpTransportTests(unittest.TestCase):
    def setUp(self):
        self.seen = []
        seen = self.seen

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.server.delay_seconds:
                    time.sleep(self.server.delay_seconds)
                length = int(self.headers["Content-Length"])
                body = json.loads(self.rfile.read(length))
                seen.append({"path": self.path, "authorization": self.headers.get("Authorization"), "session": self.headers.get("Mcp-Session-Id"), "protocol": self.headers.get("Mcp-Protocol-Version"), "body": body})
                if self.server.reject:
                    status, payload, session_id = 401, {"code": "UNAUTHENTICATED"}, None
                elif body["method"] == "initialize":
                    status, payload, session_id = 200, {"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2025-06-18"}}, "fixture-session"
                elif body["method"] == "notifications/initialized":
                    status, payload, session_id = 202, None, None
                else:
                    status, payload, session_id = 200, "event: message\ndata: {\"jsonrpc\": \"2.0\", \"id\": \"" + body["id"] + "\", \"result\": {\"structuredContent\": {\"schema_version\": \"1.0\"}}}\n\n", None
                self.send_response(status)
                if session_id:
                    self.send_header("Mcp-Session-Id", session_id)
                if payload is not None:
                    encoded = (payload.encode() if isinstance(payload, str) else json.dumps(payload).encode())
                    self.send_header("Content-Type", "text/event-stream" if isinstance(payload, str) else "application/json")
                    self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                if payload is not None:
                    try:
                        self.wfile.write(encoded)
                    except BrokenPipeError:
                        pass

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.reject = False
        self.server.delay_seconds = 0
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.transport = McpHttpTransport(f"http://127.0.0.1:{self.server.server_port}/mcp")

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_negotiates_session_then_sends_bearer_tool_call(self):
        tokens = iter(("token-1", "token-2", "token-3"))
        reply = self.transport(lambda: next(tokens), {"name": "legion_search_corpus", "arguments": {"query": "least privilege"}})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.body, {"schema_version": "1.0"})
        self.assertEqual([request["body"]["method"] for request in self.seen], ["initialize", "notifications/initialized", "tools/call"])
        self.assertEqual([request["authorization"] for request in self.seen], ["Bearer token-1", "Bearer token-2", "Bearer token-3"])
        self.assertIsNone(self.seen[0]["session"])
        self.assertEqual(self.seen[2]["session"], "fixture-session")
        self.assertEqual(self.seen[2]["protocol"], "2025-06-18")
        self.assertEqual(self.seen[2]["body"]["params"]["name"], "legion_search_corpus")

    def test_preserves_generic_http_authentication_failure(self):
        self.server.reject = True
        reply = self.transport("bad-token", {"name": "legion_search_corpus", "arguments": {}})
        self.assertEqual(reply.status_code, 401)
        self.assertEqual(reply.body, {"code": "UNAUTHENTICATED"})
        self.assertEqual(len(self.seen), 1)

    def test_timeout_is_a_deadline_error(self):
        self.server.delay_seconds = 0.05
        transport = McpHttpTransport(f"http://127.0.0.1:{self.server.server_port}/mcp", timeout_seconds=0.01)
        with self.assertRaisesRegex(McpTransportError, "DEADLINE_EXCEEDED"):
            transport("token", {"name": "legion_search_corpus", "arguments": {}})

    def test_rejects_non_positive_or_non_finite_deadlines(self):
        endpoint = f"http://127.0.0.1:{self.server.server_port}/mcp"
        for timeout in (0, -1, float("inf")):
            with self.assertRaisesRegex(ValueError, "timeout"):
                McpHttpTransport(endpoint, timeout_seconds=timeout)


if __name__ == "__main__":
    unittest.main()
