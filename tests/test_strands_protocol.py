import socket
import struct
import unittest

from experiments.strands.protocol import MAX_FRAME_BYTES, ProxyRefused, encode, receive, request_schema


class StrandsProtocolTests(unittest.TestCase):
    def test_bounded_round_trip(self):
        left, right = socket.socketpair()
        with left, right:
            value = {"operation": "start", "arguments": {}}
            left.sendall(encode(value))
            self.assertEqual(receive(right), value)

    def test_oversize_header_rejected_without_reading_body(self):
        left, right = socket.socketpair()
        with left, right:
            left.sendall(struct.pack("!I", MAX_FRAME_BYTES + 1))
            with self.assertRaises(ProxyRefused):
                receive(right)

    def test_duplicate_keys_rejected(self):
        left, right = socket.socketpair()
        with left, right:
            body = b'{"operation":"start","operation":"model","arguments":{}}'
            left.sendall(struct.pack("!I", len(body)) + body)
            with self.assertRaises(ProxyRefused):
                receive(right)

    def test_authority_ids_and_arbitrary_operations_rejected(self):
        for value in ({"operation": "shell", "arguments": {}},
                      {"operation": "model", "arguments": {}, "mission_id": "forged"},
                      {"operation": ["model"], "arguments": {}}):
            with self.subTest(value=value), self.assertRaises(ProxyRefused):
                request_schema(value)
