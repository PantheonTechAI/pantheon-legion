"""Closed, bounded IPC framing. Channel identity is supplied by the launcher."""

from __future__ import annotations

import json
import socket
import struct

MAX_FRAME_BYTES = 256 * 1024
OPERATIONS = frozenset({"start", "model", "tabula_search", "fixture_record_review", "finish", "telemetry"})


class ProxyRefused(RuntimeError):
    """Safe code only; never propagate transport/model/tool exception bodies."""


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("DUPLICATE_KEY")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("INVALID_CONSTANT")


def encode(value):
    try:
        body = json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":")).encode("utf-8")
        if not 1 <= len(body) <= MAX_FRAME_BYTES:
            raise ValueError
        return struct.pack("!I", len(body)) + body
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ProxyRefused("INVALID_FRAME") from None


def _read(sock, length):
    chunks = []
    remaining = length
    while remaining:
        block = sock.recv(remaining)
        if not block:
            raise ProxyRefused("INCOMPLETE_FRAME")
        chunks.append(block)
        remaining -= len(block)
    return b"".join(chunks)


def receive(sock):
    size = struct.unpack("!I", _read(sock, 4))[0]
    if not 1 <= size <= MAX_FRAME_BYTES:
        raise ProxyRefused("INVALID_FRAME_SIZE")
    try:
        return json.loads(_read(sock, size), object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ProxyRefused("INVALID_FRAME") from None


def request_schema(value):
    if (not isinstance(value, dict) or set(value) != {"operation", "arguments"}
            or not isinstance(value["operation"], str) or value["operation"] not in OPERATIONS
            or not isinstance(value["arguments"], dict)):
        raise ProxyRefused("INVALID_REQUEST")
    return value["operation"], value["arguments"]


class ProxyClient:
    def __init__(self, path):
        self.path = path

    def call(self, operation, **arguments):
        request = {"operation": operation, "arguments": arguments}
        request_schema(request)
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(120)
                sock.connect(self.path)
                sock.sendall(encode(request))
                response = receive(sock)
        except (OSError, ValueError, TypeError, ProxyRefused):
            raise ProxyRefused("BRIDGE_UNAVAILABLE") from None
        if not isinstance(response, dict) or response.get("ok") is not True or set(response) != {"ok", "result"}:
            raise ProxyRefused("REQUEST_REFUSED")
        return response["result"]
