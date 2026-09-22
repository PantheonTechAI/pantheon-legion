"""Fresh-project-only live cognition fixture; Tabula owns its data and seed."""

import json
import os
import re

from .tabula_stack import DisposableStackError, TabulaDisposableStack, _environment_values


SERVICES = ("neo4j", "postgres", "rushdb", "console-db", "console", "mcp-server")


class CognitionTabulaStack(TabulaDisposableStack):
    def _preflight_command(self):
        if not re.fullmatch(r"pantheon-federation-[a-z0-9][a-z0-9-]*", self.project_name):
            raise DisposableStackError("invalid cognition fixture project name")
        command = super()._preflight_command()
        overlay = self.tabula_root / "docker-compose.cognition.yml"
        if not overlay.is_file():
            raise DisposableStackError("Tabula cognition isolation overlay is required")
        index = command.index("up")
        return command[:index] + ["-f", str(overlay)] + command[index:]

    def start(self, docker_introspection_url):
        command = self._preflight_command()
        prefix = command[:command.index("up")]
        values = _environment_values(self.env_file)
        if values.get("RUSHDB_PORT") != values.get("PANTHEON_FEDERATION_RUSHDB_PORT"):
            raise DisposableStackError("provisioning port must equal the disposable RushDB port")
        environment = dict(os.environ)
        # Compose and the existing provisioner must read the same dedicated file,
        # not inherited shell credentials (including a token from a prior run).
        for key in values:
            environment.pop(key, None)
        environment["PANTHEON_STS_INTROSPECTION_URL"] = docker_introspection_url
        environment["PROJECT_NAME"] = self.project_name
        config = self.runner(prefix + ["config", "--format", "json"], cwd=self.tabula_root,
                             env=environment, capture_output=True, text=True, check=True)
        configuration = json.loads(config.stdout)
        if configuration.get("name") != self.project_name:
            raise DisposableStackError("rendered project name does not match the fixture")
        self._validate_configuration(configuration)
        for operation in (["ps", "--all", "--quiet"], ["volume", "ls", "--quiet"],
                          ["network", "ls", "--quiet"]):
            existing = self.runner(["docker", *operation, "--filter",
                "label=com.docker.compose.project=" + self.project_name],
                capture_output=True, text=True, check=True)
            if existing.stdout.strip():
                raise DisposableStackError("fixture project already owns resources; refusing reuse or cleanup")
        # Cleanup ownership begins only after the read-only configuration and
        # collision gates. A partially failed startup still needs cleanup.
        self._compose_prefix, self._environment = prefix, environment
        self.runner(prefix + ["up", "--detach", "--wait", *SERVICES[:4]],
                    cwd=self.tabula_root, env=environment, check=True)
        self.runner(["bash", "scripts/provision_token.sh", str(self.env_file)],
                    cwd=self.tabula_root, env=environment, capture_output=True, text=True, check=True)
        self.runner(command, cwd=self.tabula_root, env=environment, check=True)
        self._seed_bindings()

    @staticmethod
    def _validate_configuration(config):
        for name in SERVICES:
            service = config["services"][name]
            if any(port.get("host_ip") != "127.0.0.1" for port in service.get("ports", [])):
                raise DisposableStackError("cognition fixture listeners must be loopback-only")
            for volume in service.get("volumes", []):
                if volume["type"] != "volume" or config["volumes"][volume["source"]].get("external"):
                    raise DisposableStackError("cognition fixture data must use project-owned volumes")
                if config["volumes"][volume["source"]]["name"] != config["name"] + "_" + volume["source"]:
                    raise DisposableStackError("cognition fixture volume name must be project-scoped")
        for name in ("console", "mcp-server"):
            settings = config["services"][name]["environment"]
            if settings.get("OTEL_ENABLED") != "false" or settings.get("HYBRID_SEARCH") != "false":
                raise DisposableStackError("cognition fixture must disable telemetry and embedding calls")
            if any(settings.get(key) != "http://127.0.0.1:9" for key in ("EMBED_OLLAMA_URL", "LLM_OLLAMA_URL")):
                raise DisposableStackError("Tabula fixture inference targets must remain disabled")
        settings = config["services"]["console"]["environment"]
        if not settings.get("CREDENTIAL_ENCRYPTION_KEY"):
            raise DisposableStackError("Console startup requires a disposable encryption key")
        if any(settings.get(key) != "false" for key in (
                "ARTIFACT_REGEN_POLL_ENABLED", "REGISTRY_SYNC_POLL_ENABLED", "NOTIFICATION_POLL_ENABLED")):
            raise DisposableStackError("cognition fixture background pollers must be disabled")

    def seed_corpus(self):
        if self._compose_prefix is None:
            raise DisposableStackError("cognition fixture is not started")
        script = (self.tabula_root / "tests/federation/seed_cognition_corpus.py").read_text()
        result = self.runner(self._compose_prefix + ["exec", "-T", "mcp-server", "python", "-"],
                             cwd=self.tabula_root, env=self._environment, input=script,
                             capture_output=True, text=True, check=True)
        # Shared write_entry may emit benign embedding-unavailable diagnostics.
        # Only its final seed metadata is returned, never raw service logs.
        return json.loads(result.stdout.splitlines()[-1])
