"""Safety gates for the real-model fixture; no Docker or live calls in unit tests."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.federation.cognition_stack import CognitionTabulaStack, SERVICES
from tests.federation.tabula_stack import DisposableStackError


def fixture_config():
    config = {"name": "pantheon-federation-test", "services": {},
              "volumes": {"data": {"name": "pantheon-federation-test_data"}}}
    for service in SERVICES:
        config["services"][service] = {"ports": [{"host_ip": "127.0.0.1"}],
            "volumes": [{"type": "volume", "source": "data"}],
            "environment": {"OTEL_ENABLED": "false", "HYBRID_SEARCH": "false",
                "CREDENTIAL_ENCRYPTION_KEY": "fixture-only-key",
                "EMBED_OLLAMA_URL": "http://127.0.0.1:9", "LLM_OLLAMA_URL": "http://127.0.0.1:9",
                "ARTIFACT_REGEN_POLL_ENABLED": "false", "REGISTRY_SYNC_POLL_ENABLED": "false",
                "NOTIFICATION_POLL_ENABLED": "false"}}
    return config


class CognitionLiveFixtureTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "docker-compose.cognition.yml").touch()
        (self.root / "tests/federation").mkdir(parents=True)
        (self.root / "tests/federation/seed_scope_bindings.sql").write_text("SELECT 1;")
        self.env = self.root / ".env.cognition"
        self.env.write_text("RUSHDB_PORT=13000\nPANTHEON_FEDERATION_RUSHDB_PORT=13000\n")
        self.calls = []
        self.existing = False
        self.fail_start = False

        def run(command, **kwargs):
            self.calls.append(command)
            output = ""
            if "tests.federation.isolation" in command:
                output = "docker compose --project-name pantheon-federation-test up --detach --wait --build mcp-server"
            elif "config" in command:
                output = json.dumps(fixture_config())
            elif "--filter" in command and self.existing:
                output = "pre-existing-resource"
            elif "up" in command and self.fail_start:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0, stdout=output)

        self.stack = CognitionTabulaStack(self.root, "pantheon-federation-test", self.env, runner=run)

    def test_existing_resources_are_never_started_or_cleaned(self):
        self.existing = True
        with self.assertRaisesRegex(DisposableStackError, "already owns"):
            self.stack.start("http://host.docker.internal:19080/v1/introspect")
        self.stack.cleanup()
        self.assertFalse(any("up" in call or "down" in call for call in self.calls))

    def test_fresh_backend_precedes_provisioning_and_apps(self):
        self.stack.start("http://host.docker.internal:19080/v1/introspect")
        starts = [i for i, call in enumerate(self.calls) if "up" in call]
        provision = next(i for i, call in enumerate(self.calls) if "scripts/provision_token.sh" in call)
        self.assertLess(starts[0], provision)
        self.assertLess(provision, starts[1])
        self.assertEqual(self.calls[provision][-1], str(self.env))
        self.stack.cleanup()
        self.assertEqual(self.calls[-1][-3:], ["down", "--volumes", "--remove-orphans"])
        self.assertIn(str(self.root / "docker-compose.cognition.yml"), self.calls[-1])

    def test_partial_startup_can_be_cleaned_but_wrong_port_cannot(self):
        self.fail_start = True
        with self.assertRaises(subprocess.CalledProcessError):
            self.stack.start("http://host.docker.internal:19080/v1/introspect")
        self.stack.cleanup()
        self.assertIn("down", self.calls[-1])
        self.calls.clear()
        self.env.write_text("RUSHDB_PORT=3030\nPANTHEON_FEDERATION_RUSHDB_PORT=13000\n")
        with self.assertRaisesRegex(DisposableStackError, "port"):
            self.stack.start("http://host.docker.internal:19080/v1/introspect")
        self.stack.cleanup()
        self.assertFalse(any("down" in call for call in self.calls))

    def test_configuration_rejects_nonisolated_resources_and_pollers(self):
        changes = [lambda c: c["services"]["console"]["ports"][0].update(host_ip="0.0.0.0"),
                   lambda c: c["services"]["console"]["volumes"][0].update(type="bind"),
                   lambda c: c["volumes"]["data"].update(external=True),
                   lambda c: c["volumes"]["data"].update(name="production_data"),
                   lambda c: c["services"]["console"]["environment"].update(NOTIFICATION_POLL_ENABLED="true"),
                   lambda c: c["services"]["mcp-server"]["environment"].update(OTEL_ENABLED="true"),
                   lambda c: c["services"]["mcp-server"]["environment"].update(HYBRID_SEARCH="true"),
                   lambda c: c["services"]["console"]["environment"].pop("CREDENTIAL_ENCRYPTION_KEY"),
                   lambda c: c["services"]["console"]["environment"].update(CREDENTIAL_ENCRYPTION_KEY=""),
                   lambda c: c["services"]["mcp-server"]["environment"].update(EMBED_OLLAMA_URL="http://other:8105"),
                   lambda c: c["services"]["console"]["environment"].update(LLM_OLLAMA_URL="http://other:11434")]
        for change in changes:
            config = deepcopy(fixture_config())
            change(config)
            with self.subTest(change=change), self.assertRaises(DisposableStackError):
                self.stack._validate_configuration(config)
