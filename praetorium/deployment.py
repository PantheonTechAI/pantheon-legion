"""AI-box deployment composition for a loopback-only Praetorium process."""

from __future__ import annotations

import argparse
import os
from wsgiref.simple_server import make_server

from aquila_api.auth import AuthenticationError, AuthentikConfig, AuthentikPrincipalMapper
from aquila_api.persistent import PersistentAquilaService

from .wsgi import PraetoriumWSGIApp


class CaddyForwardAuthAuthenticator:
    """Trust Authentik headers only from the local Caddy reverse proxy."""

    def __init__(self, mapper: AuthentikPrincipalMapper) -> None:
        self.mapper = mapper

    def authenticate_request(self, environ):
        if environ.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}:
            raise AuthenticationError("UNTRUSTED_PROXY")
        subject = environ.get("HTTP_X_AUTHENTIK_UID") or environ.get("HTTP_X_AUTHENTIK_USERNAME")
        groups = [group.strip() for group in environ.get("HTTP_X_AUTHENTIK_GROUPS", "").replace(";", ",").split(",") if group.strip()]
        return self.mapper.map_claims({"iss": os.environ["LEGION_OIDC_ISSUER"], "aud": os.environ["LEGION_OIDC_AUDIENCE"], "sub": subject, "groups": groups})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Praetorium behind local Caddy forward-auth.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8101)
    args = parser.parse_args()
    required = ("LEGION_DATABASE", "LEGION_OIDC_ISSUER", "LEGION_OIDC_AUDIENCE", "TABULA_CONSOLE_URL")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit(f"missing required configuration: {', '.join(missing)}")
    service = PersistentAquilaService(os.environ["LEGION_DATABASE"])
    mapper = AuthentikPrincipalMapper(AuthentikConfig(issuer=os.environ["LEGION_OIDC_ISSUER"], audience=os.environ["LEGION_OIDC_AUDIENCE"]))
    app = PraetoriumWSGIApp(service, CaddyForwardAuthAuthenticator(mapper), tabula_console_url=os.environ["TABULA_CONSOLE_URL"])
    try:
        make_server(args.host, args.port, app).serve_forever()
    finally:
        service.close()


if __name__ == "__main__":
    main()
