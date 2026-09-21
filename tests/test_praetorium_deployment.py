import os
import unittest
from unittest.mock import Mock, patch

from aquila_api.auth import AuthentikConfig, AuthentikPrincipalMapper
from praetorium.deployment import (
    CaddyForwardAuthAuthenticator,
    runtime_read_model_from_environment,
)


class CaddyForwardAuthAuthenticatorTests(unittest.TestCase):
    def setUp(self):
        mapper = AuthentikPrincipalMapper(AuthentikConfig(issuer="https://auth.example/", audience="aquila"))
        self.authenticator = CaddyForwardAuthAuthenticator(mapper)

    def test_authentik_pipe_separated_groups_map_to_legion_roles(self):
        with patch.dict(os.environ, {"LEGION_OIDC_ISSUER": "https://auth.example/", "LEGION_OIDC_AUDIENCE": "aquila"}):
            principal = self.authenticator.authenticate_request(
                {
                    "REMOTE_ADDR": "127.0.0.1",
                    "HTTP_X_AUTHENTIK_UID": "user-1",
                    "HTTP_X_AUTHENTIK_GROUPS": "tabula-admins|legion/mission-owners",
                }
            )

        self.assertEqual(principal.subject, "user-1")
        self.assertEqual(principal.roles, frozenset({"MISSION_OWNER"}))

    def test_runtime_projection_is_optional_and_uses_bounded_timeouts(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(runtime_read_model_from_environment(), (None, None))

        engine = Mock()
        with patch.dict(
            os.environ,
            {
                "LEGION_RUNTIME_DATABASE_URL": "postgresql+psycopg://test/db",
                "LEGION_RUNTIME_POOL_TIMEOUT_MS": "250",
                "LEGION_RUNTIME_CONNECT_TIMEOUT_MS": "1000",
                "LEGION_RUNTIME_STATEMENT_TIMEOUT_MS": "500",
            },
            clear=True,
        ), patch("praetorium.deployment.create_engine", return_value=engine) as create:
            read_model, created_engine = runtime_read_model_from_environment()
        self.assertIsNotNone(read_model)
        self.assertIs(created_engine, engine)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["pool_timeout"], 0.25)
        self.assertEqual(kwargs["connect_args"]["connect_timeout"], 1)
        self.assertEqual(
            kwargs["connect_args"]["options"], "-c statement_timeout=500"
        )

    def test_runtime_projection_rejects_out_of_range_timeout(self):
        with patch.dict(
            os.environ,
            {
                "LEGION_RUNTIME_DATABASE_URL": "postgresql+psycopg://test/db",
                "LEGION_RUNTIME_POOL_TIMEOUT_MS": "5000",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(SystemExit, "between 50 and 1000"):
                runtime_read_model_from_environment()
