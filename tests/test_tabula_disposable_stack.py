import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.federation.tabula_stack import TabulaDisposableStack


class TabulaDisposableStackTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "tests/federation").mkdir(parents=True)
        (self.root / "tests/federation/seed_scope_bindings.sql").write_text("INSERT INTO tabula_scope_bindings VALUES ('fixture');")
        self.env_file = self.root / ".env"
        self.env_file.write_text("PANTHEON_FEDERATION_MCP_PORT=18100\nCONSOLE_DB_USER=fixture\nCONSOLE_DB_NAME=fixture_db\n")
        self.calls = []

        def runner(command, **kwargs):
            self.calls.append((command, kwargs))
            if command[1:3] == ["-m", "tests.federation.isolation"]:
                return subprocess.CompletedProcess(command, 0, stdout="docker compose --project-name pantheon-federation-test up --detach --wait --build mcp-server\n")
            return subprocess.CompletedProcess(command, 0)

        self.stack = TabulaDisposableStack(self.root, "pantheon-federation-test", self.env_file, runner=runner)

    def tearDown(self):
        self.directory.cleanup()

    def test_starts_only_preflight_command_then_seeds_and_cleans_project(self):
        self.stack.start("http://host.docker.internal:19080/v1/introspect")
        self.assertEqual(self.calls[0][0][1:3], ["-m", "tests.federation.isolation"])
        self.assertEqual(self.calls[1][0][:2], ["docker", "compose"])
        self.assertEqual(self.calls[1][1]["env"]["PANTHEON_STS_INTROSPECTION_URL"], "http://host.docker.internal:19080/v1/introspect")
        self.assertEqual(self.calls[2][0][-3:], ["alembic", "upgrade", "head"])
        self.assertIn("console-db", self.calls[3][0])
        self.assertIn("INSERT INTO", self.calls[3][1]["input"])
        self.assertEqual(self.stack.mcp_endpoint, "http://127.0.0.1:18100/mcp")
        self.stack.restart_mcp()
        self.assertEqual(
            self.calls[4][0][-4:],
            ["restart", "--timeout", "10", "mcp-server"],
        )
        self.assertEqual(
            self.calls[5][0][-4:],
            ["up", "--detach", "--wait", "mcp-server"],
        )
        self.stack.cleanup()
        self.assertEqual(self.calls[6][0][-3:], ["down", "--volumes", "--remove-orphans"])
        self.assertEqual(self.calls[6][1]["env"]["PANTHEON_STS_INTROSPECTION_URL"], "http://host.docker.internal:19080/v1/introspect")

    def test_cleanup_before_start_is_a_noop(self):
        self.stack.cleanup()
        self.assertEqual(self.calls, [])

    def test_restart_before_start_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "not started"):
            self.stack.restart_mcp()


if __name__ == "__main__":
    unittest.main()
