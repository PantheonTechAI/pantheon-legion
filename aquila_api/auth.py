"""Authentik/OIDC identity mapping without a JWT-library dependency.

Cryptographic token verification belongs to an injectable verifier. This module
starts from verified OIDC claims and applies Legion's identity and role rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from legion_kernel import Principal, PrincipalType


class AuthenticationError(ValueError):
    """Raised when a bearer credential or verified claims are unacceptable."""


class ClaimsVerifier(Protocol):
    def verify(self, token: str) -> dict[str, Any]:
        """Verify signature, issuer, audience, expiry, and return claims."""


@dataclass(frozen=True)
class AuthentikConfig:
    issuer: str
    audience: str
    group_roles: dict[str, frozenset[str]] = field(
        default_factory=lambda: {
            "legion/mission-owners": frozenset({"MISSION_OWNER"}),
            "legion/mission-operators": frozenset({"OPERATOR"}),
            "legion/mission-approvers": frozenset({"APPROVER"}),
            "legion/mission-observers": frozenset({"OBSERVER"}),
        }
    )


class AuthentikPrincipalMapper:
    """Map already verified Authentik claims into a canonical Principal."""

    def __init__(self, config: AuthentikConfig) -> None:
        self.config = config

    def map_claims(self, claims: dict[str, Any]) -> Principal:
        if claims.get("iss") != self.config.issuer:
            raise AuthenticationError("INVALID_ISSUER")
        if not self._audience_matches(claims.get("aud")):
            raise AuthenticationError("INVALID_AUDIENCE")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("MISSING_SUBJECT")

        groups = claims.get("groups", [])
        if not isinstance(groups, list) or not all(isinstance(group, str) for group in groups):
            raise AuthenticationError("INVALID_GROUPS")
        roles = set()
        for group in groups:
            roles.update(self.config.group_roles.get(group, frozenset()))

        principal_type = (
            PrincipalType.WORKLOAD
            if claims.get("legion_actor_type") == "WORKLOAD"
            else PrincipalType.HUMAN
        )
        return Principal(
            type=principal_type,
            subject=subject,
            roles=frozenset(roles),
        )

    def _audience_matches(self, audience: Any) -> bool:
        if isinstance(audience, str):
            return audience == self.config.audience
        if isinstance(audience, list):
            return self.config.audience in audience
        return False


class BearerAuthenticator:
    """Authenticate an HTTP Authorization header through an injected verifier."""

    def __init__(self, verifier: ClaimsVerifier, mapper: AuthentikPrincipalMapper) -> None:
        self.verifier = verifier
        self.mapper = mapper

    def authenticate(self, authorization_header: str | None) -> Principal:
        if not authorization_header:
            raise AuthenticationError("UNAUTHENTICATED")
        scheme, separator, token = authorization_header.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token:
            raise AuthenticationError("UNAUTHENTICATED")
        try:
            claims = self.verifier.verify(token)
        except AuthenticationError:
            raise
        except Exception as exc:
            raise AuthenticationError("INVALID_TOKEN") from exc
        return self.mapper.map_claims(claims)
