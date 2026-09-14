import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.federation.http_transport import McpHttpTransport


class McpHttpTransportTests(unittest.TestCase):
    def setUp(self):
        self.seen = {}
        seen = self.seen

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                seen.update(path=self.path, authorization=self.headers.get("Authorization"), body=json.loads(self.rfile.read(length)))
                status, payload = self.server.reply
                encoded = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.reply = (200, {"jsonrpc": "2.0", "result": {"structuredContent": {"schema_version": "1.0"}}})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.transport = McpHttpTransport(f"http://127.0.0.1:{self.server.server_port}/mcp")

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_sends_bearer_json_rpc_and_unwraps_structured_content(self):
        reply = self.transport("fixture-token", {"name": "legion_search_corpus", "arguments": {"query": "least privilege"}})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(reply.body, {"schema_version": "1.0"})
        self.assertEqual(self.seen["path"], "/mcp")
        self.assertEqual(self.seen["authorization"], "Bearer fixture-token")
        self.assertEqual(self.seen["body"]["method"], "tools/call")
        self.assertEqual(self.seen["body"]["params"]["name"], "legion_search_corpus")

    def test_preserves_generic_http_authentication_failure(self):
        self.server.reply = (401, {"code": "UNAUTHENTICATED"})
        reply = self.transport("bad-token", {"name": "legion_search_corpus", "arguments": {}})
        self.assertEqual(reply.status_code, 401)
        self.assertEqual(reply.body, {"code": "UNAUTHENTICATED"})


if __name__ == "__main__":
    unittest.main()
