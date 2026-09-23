"""Actual launcher network/socket restrictions and native trace leak refusal."""

import os
from pathlib import Path
import socket
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from uuid import uuid4

from experiments.strands.bridge import DockerWorker


@unittest.skipUnless(os.environ.get("LEGION_STRANDS_ACCEPTANCE") == "1", "opt-in actual isolated image")
class BoundarySurfaceTests(unittest.TestCase):
    def run_isolated(self, script, *arguments):
        worker = DockerWorker()
        execution = str(uuid4())
        name = "legion-strands-" + execution
        with tempfile.TemporaryDirectory(prefix="legion-boundary-surfaces-") as directory:
            command = worker.command(SimpleNamespace(execution_id=execution), directory, name)
            command[-1:-1] = ["--entrypoint", "python"]
            command.extend(["-c", script, *arguments])
            try:
                result = subprocess.run(command, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(result.stdout.strip(), b"BOUNDARY_PASS")
                self.assertEqual(result.stderr, b"")
            finally:
                worker.stop_owned(name, execution)

    def test_all_endpoint_classes_and_other_private_channel_are_inaccessible(self):
        with tempfile.TemporaryDirectory(prefix="legion-other-worker-channel-") as directory, socket.socket(socket.AF_UNIX) as other:
            path = str(Path(directory) / "worker.sock")
            other.bind(path)
            other.listen(1)
            self.run_isolated('''
import pathlib, socket, sys
assert [name for _, name in socket.if_nameindex()] == ["lo"]
targets = [("192.168.15.17",8000), ("192.168.15.16",8100), ("192.168.15.16",5434),
           ("127.0.0.1",5434), ("169.254.169.254",80), ("192.0.2.1",443)]
for address in targets:
    with socket.socket() as channel:
        channel.settimeout(0.2)
        assert channel.connect_ex(address) != 0
assert not pathlib.Path(sys.argv[1]).exists()
with socket.socket(socket.AF_UNIX) as channel:
    assert channel.connect_ex(sys.argv[1]) != 0
for path in ("/var/run/docker.sock", "/home/jtdauria/.ssh", "/home/jtdauria/pantheon-legion"):
    assert not pathlib.Path(path).exists()
print("BOUNDARY_PASS")
''', path)

    def test_events_attributes_exceptions_are_detected_before_safe_trace_export(self):
        self.run_isolated('''
import json, logging
import experiments.strands.worker
from experiments.strands.telemetry import TraceCapture, SENTINELS
capture = TraceCapture("1" * 32, "2" * 16)
tracer = capture.provider.get_tracer("synthetic-boundary-test")
for sentinel in SENTINELS:
    logging.error(sentinel)
    with tracer.start_as_current_span("synthetic") as span:
        span.set_attribute("prohibited", sentinel)
        span.add_event("synthetic", {"prohibited": sentinel})
        span.record_exception(ValueError(sentinel))
result = capture.finish()
assert result["leak_detected"] is True
assert result["spans"]
assert all(sentinel not in json.dumps(result) for sentinel in SENTINELS)
print("BOUNDARY_PASS")
''')
