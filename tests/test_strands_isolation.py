"""Exercise the actual launcher restrictions, not an in-process socket mock."""

import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from uuid import uuid4

from experiments.strands.bridge import DockerWorker


@unittest.skipUnless(os.environ.get("LEGION_STRANDS_ACCEPTANCE") == "1", "opt-in Docker isolation test")
class StrandsIsolationTests(unittest.TestCase):
    def test_same_launcher_blocks_network_host_files_and_rootfs_writes(self):
        worker = DockerWorker()
        execution_id = str(uuid4())
        name = "legion-strands-" + execution_id
        with tempfile.TemporaryDirectory(prefix="legion-strands-isolation-") as directory:
            command = worker.command(SimpleNamespace(execution_id=execution_id), directory, name)
            command[-1:-1] = ["--entrypoint", "python"]
            command.extend(["-c", '''
import errno, os, pathlib, socket, sys
assert os.getuid() != 0
assert [name for _, name in socket.if_nameindex()] == ["lo"]
with socket.socket() as sock:
    sock.settimeout(1)
    assert sock.connect_ex(("192.0.2.1", 443)) != 0
assert not pathlib.Path(sys.argv[1]).exists()
assert not pathlib.Path("/var/run/docker.sock").exists()
assert "LEGION_RUNTIME_TEST_DATABASE_URL" not in os.environ
assert "AWS_ACCESS_KEY_ID" not in os.environ
status = pathlib.Path("/proc/self/status").read_text()
assert "CapEff:\\t0000000000000000" in status
assert "NoNewPrivs:\\t1" in status
try:
    pathlib.Path("/opt/legion/write-probe").write_text("synthetic")
except OSError as exc:
    assert exc.errno in (errno.EROFS, errno.EACCES)
else:
    raise AssertionError("ROOTFS_WRITE_ALLOWED")
print("ISOLATION_PASS")
''', str(Path(__file__).resolve().parents[1])])
            try:
                result = subprocess.run(command, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(result.stdout.strip(), b"ISOLATION_PASS")
            finally:
                worker.stop_owned(name, execution_id)
