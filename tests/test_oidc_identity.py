import unittest

from aquila_api.auth import (
    AuthenticationError,
    AuthentikConfig,
    AuthentikPrincipalMapper,
    BearerAuthenticator,
)
from legion_kernel import PrincipalType


class FakeVerifier:
    def __init__(self, claims=None, error=None):
        self.claims = claims or {}
        self.error = error

    def verify(self, token):
        if self.error:
            raise self.error
        if token != "valid-token":
            raise ValueError("bad token")
        return self.claims


class OidcIdentityTests(unittest.TestCase):
    def setUp(self):
        self.config = AuthentikConfig(
            issuer="https://authentik.example/application/o/legion/",
            audience="legion-aquila",
        )
        self.mapper = AuthentikPrincipalMapper(self.config)
        self.claims = {
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "sub": "user-123",
            "groups": ["legion/mission-owners", "legion/mission-approvers", "unmapped"],
        }

    def test_human_claims_map_only_declared_roles(self):
        principal = self.mapper.map_claims(self.claims)
        self.assertEqual(principal.type, PrincipalType.HUMAN)
        self.assertEqual(principal.subject, "user-123")
        self.assertEqual(principal.roles, frozenset({"MISSION_OWNER", "APPROVER"}))

    def test_multi_audience_claim_is_supported(self):
        claims = dict(self.claims, aud=["other-service", self.config.audience])
        self.assertEqual(self.mapper.map_claims(claims).subject, "user-123")

    def test_invalid_issuer_audience_and_subject_fail(self):
        for invalid in (
            dict(self.claims, iss="wrong"),
            dict(self.claims, aud="wrong"),
            dict(self.claims, sub=""),
        ):
            with self.assertRaises(AuthenticationError):
                self.mapper.map_claims(invalid)

    def test_workload_claim_is_not_promoted_to_human(self):
        principal = self.mapper.map_claims(dict(self.claims, legion_actor_type="WORKLOAD"))
        self.assertEqual(principal.type, PrincipalType.WORKLOAD)

    def test_bearer_authenticator_requires_valid_header_and_verifier(self):
        authenticator = BearerAuthenticator(FakeVerifier(self.claims), self.mapper)
        self.assertEqual(
            authenticator.authenticate("Bearer valid-token").subject,
            "user-123",
        )
        for header in (None, "Basic value", "Bearer", "Bearer "):
            with self.assertRaises(AuthenticationError):
                authenticator.authenticate(header)
        with self.assertRaises(AuthenticationError) as error:
            BearerAuthenticator(FakeVerifier(error=ValueError()), self.mapper).authenticate(
                "Bearer valid-token"
            )
        self.assertEqual(str(error.exception), "INVALID_TOKEN")
