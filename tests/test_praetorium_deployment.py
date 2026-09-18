import os
import unittest
from unittest.mock import patch

from aquila_api.auth import AuthentikConfig, AuthentikPrincipalMapper
from praetorium.deployment import CaddyForwardAuthAuthenticator


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
