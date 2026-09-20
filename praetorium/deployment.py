"""AI-box deployment composition for a loopback-only Praetorium process."""

from __future__ import annotations

import argparse
import os
from uuid import UUID
from wsgiref.simple_server import make_server

from sqlalchemy import create_engine

from aquila_api.auth import AuthenticationError, AuthentikConfig, AuthentikPrincipalMapper
from aquila_api.persistent import PersistentAquilaService
from legion_runtime import PostgreSQLAgentStore, RepositoryMissionOrganizationReadModel

from .wsgi import PraetoriumWSGIApp


class CaddyForwardAuthAuthenticator:
    """Trust Authentik headers only from the local Caddy reverse proxy."""

    def __init__(self, mapper: AuthentikPrincipalMapper) -> None:
        self.mapper = mapper

    def authenticate_request(self, environ):
        if environ.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}:
            raise AuthenticationError("UNTRUSTED_PROXY")
        subject = environ.get("HTTP_X_AUTHENTIK_UID") or environ.get("HTTP_X_AUTHENTIK_USERNAME")
        groups = [
            group.strip()
            for group in environ.get("HTTP_X_AUTHENTIK_GROUPS", "").replace("|", ",").replace(";", ",").split(",")
            if group.strip()
        ]
        return self.mapper.map_claims({"iss": os.environ["LEGION_OIDC_ISSUER"], "aud": os.environ["LEGION_OIDC_AUDIENCE"], "sub": subject, "groups": groups})


def _bounded_milliseconds(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise SystemExit(f"{name} must be between {minimum} and {maximum}")
    return value


def runtime_read_model_from_environment():
    database_url = os.environ.get("LEGION_RUNTIME_DATABASE_URL", "").strip()
    if not database_url:
        return None, None
    pool_ms = _bounded_milliseconds("LEGION_RUNTIME_POOL_TIMEOUT_MS", 250, 50, 1000)
    connect_ms = _bounded_milliseconds(
        "LEGION_RUNTIME_CONNECT_TIMEOUT_MS", 1000, 250, 3000
    )
    statement_ms = _bounded_milliseconds(
        "LEGION_RUNTIME_STATEMENT_TIMEOUT_MS", 500, 100, 2000
    )
    engine = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        pool_timeout=pool_ms / 1000,
        connect_args={
            "connect_timeout": max(1, (connect_ms + 999) // 1000),
            "options": f"-c statement_timeout={statement_ms}",
        },
    )
    store = PostgreSQLAgentStore(database_url, engine=engine)
    return RepositoryMissionOrganizationReadModel(store), engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Praetorium behind local Caddy forward-auth.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8106)
    args = parser.parse_args()
    required = (
        "LEGION_DATABASE",
        "LEGION_OIDC_ISSUER",
        "LEGION_OIDC_AUDIENCE",
        "TABULA_CONSOLE_URL",
        "LEGION_DEFAULT_ORGANIZATION_ID",
        "LEGION_DEFAULT_WORKSPACE_ID",
    )
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit(f"missing required configuration: {', '.join(missing)}")
    try:
        organization_id = str(UUID(os.environ["LEGION_DEFAULT_ORGANIZATION_ID"]))
        workspace_id = str(UUID(os.environ["LEGION_DEFAULT_WORKSPACE_ID"]))
    except ValueError as exc:
        raise SystemExit("LEGION_DEFAULT_ORGANIZATION_ID and LEGION_DEFAULT_WORKSPACE_ID must be UUIDs") from exc
    service = PersistentAquilaService(os.environ["LEGION_DATABASE"])
    organization_read_model, runtime_engine = runtime_read_model_from_environment()
    mapper = AuthentikPrincipalMapper(AuthentikConfig(issuer=os.environ["LEGION_OIDC_ISSUER"], audience=os.environ["LEGION_OIDC_AUDIENCE"]))
    app = PraetoriumWSGIApp(
        service,
        CaddyForwardAuthAuthenticator(mapper),
        tabula_console_url=os.environ["TABULA_CONSOLE_URL"],
        organization_id=organization_id,
        workspace_id=workspace_id,
        organization_read_model=organization_read_model,
    )
    try:
        make_server(args.host, args.port, app).serve_forever()
    finally:
        service.close()
        if runtime_engine is not None:
            runtime_engine.dispose()


if __name__ == "__main__":
    main()
