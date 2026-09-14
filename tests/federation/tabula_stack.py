"""Adapter that delegates disposable Tabula startup to Tabula's safety preflight."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Callable


class DisposableStackError(RuntimeError):
    """The external preflight did not return a safe, executable Compose plan."""


@dataclass
class TabulaDisposableStack:
    tabula_root: Path
    project_name: str
    env_file: Path
    runner: Callable = subprocess.run
    _compose_prefix: list[str] | None = field(default=None, init=False)
    _environment: dict[str, str] | None = field(default=None, init=False)

    @property
    def mcp_endpoint(self) -> str:
        values = _environment_values(self.env_file)
        port = values.get("PANTHEON_FEDERATION_MCP_PORT")
        if not port or not port.isdigit():
            raise DisposableStackError("disposable environment is missing PANTHEON_FEDERATION_MCP_PORT")
        return f"http://127.0.0.1:{port}/mcp"

    def start(self, docker_introspection_url: str) -> None:
        """Start only the preflight-approved project, then seed its Console database."""
        compose = self._preflight_command()
        environment = dict(os.environ)
        environment["PANTHEON_STS_INTROSPECTION_URL"] = docker_introspection_url
        prefix = compose[:compose.index("up")]
        # Register cleanup before Compose can have created a partial project.
        self._compose_prefix = prefix
        self._environment = environment
        self.runner(compose, cwd=self.tabula_root, env=environment, check=True)
        values = _environment_values(self.env_file)
        seed = (self.tabula_root / "tests/federation/seed_scope_bindings.sql").read_text()
        self.runner(
            prefix + [
                "exec", "-T", "console-db", "psql", "-v", "ON_ERROR_STOP=1",
                "-U", values.get("CONSOLE_DB_USER", "console"),
                "-d", values.get("CONSOLE_DB_NAME", "console"), "-f", "-",
            ],
            cwd=self.tabula_root, env=environment, input=seed, text=True, check=True,
        )

    def cleanup(self) -> None:
        """Remove only the project that this adapter successfully started."""
        if self._compose_prefix is None:
            return
        self.runner(self._compose_prefix + ["down", "--volumes"], cwd=self.tabula_root, env=self._environment, check=True)
        self._compose_prefix = None
        self._environment = None

    def _preflight_command(self) -> list[str]:
        environment = dict(os.environ, PANTHEON_FEDERATION_DISPOSABLE="1")
        result = self.runner(
            [
                sys.executable, "-m", "tests.federation.isolation",
                "--tabula-root", str(self.tabula_root),
                "--project-name", self.project_name,
                "--env-file", str(self.env_file),
            ],
            cwd=self.tabula_root, env=environment, text=True, capture_output=True, check=True,
        )
        command = shlex.split(result.stdout.strip())
        if command[:2] != ["docker", "compose"] or "up" not in command:
            raise DisposableStackError("Tabula preflight did not return a Compose startup command")
        return command


def _environment_values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    return values
