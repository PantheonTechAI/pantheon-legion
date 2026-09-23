"""Disposable scripted inference HTTP peer. Test requests never enter product state."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time
from threading import Thread


REASONING_SENTINEL = "EXPLICIT_REASONING_SENTINEL_DO_NOT_RETAIN"


def tool_response(arguments='{"query":"Find architecture evidence"}', name="tabula_search"):
    return {"id": "response-initial", "choices": [{"index": 0, "finish_reason": "tool_calls",
        "message": {"role": "assistant", "content": None, "reasoning": REASONING_SENTINEL,
            "tool_calls": [{"id": "call-one", "type": "function", "function": {"name": name, "arguments": arguments}}]}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 40, "completion_tokens_details": {"reasoning_tokens": 10}}}


def final_response(content="The supplied architecture evidence supports bounded authorized cognition."):
    return {"id": "response-final", "choices": [{"index": 0, "finish_reason": "stop",
        "message": {"role": "assistant", "content": content, "reasoning": REASONING_SENTINEL}}],
        "usage": {"prompt_tokens": 150, "completion_tokens": 30}}


@contextmanager
def inference_server(responses=None):
    class Peer:
        def __init__(self):
            self.requests = []
            self.responses = list(responses if responses is not None else [tool_response(), final_response()])
            self.models = [{"id": "model-a", "max_model_len": 32768}]
            self.version = "1"
            self.delays = []

    peer = Peer()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body):
            encoded = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(status)
            if 300 <= status < 400:
                self.send_header("Location", peer.origin + "/redirect-target")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            peer.requests.append((self.path, None, dict(self.headers)))
            self.reply(200, {"data": peer.models} if self.path == "/v1/models" else
                       {"version": peer.version} if self.path == "/version" else {})

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            peer.requests.append((self.path, request, dict(self.headers)))
            response = peer.responses.pop(0) if peer.responses else final_response()
            if callable(response):
                response = response(request)
            if peer.delays:
                time.sleep(peer.delays.pop(0))
            status, body = response if isinstance(response, tuple) else (200, response)
            self.reply(status, body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    peer.origin = "http://127.0.0.1:" + str(server.server_port)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield peer
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
