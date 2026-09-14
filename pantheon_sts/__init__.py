"""Deterministic Pantheon STS conformance fixture.

This package supplies the real HTTP and cryptographic seams needed to test the
Legion--Tabula federated-read contract. It is not a production deployment.
"""

from .assertions import Ed25519AssertionVerifier, sign_assertion
from .service import InMemorySecurityTokenService, IssuedToken, STSAuditEvent
from .wsgi import STSWSGIApp, StaticServiceAuthenticator

__all__ = [
    "Ed25519AssertionVerifier", "InMemorySecurityTokenService", "IssuedToken",
    "STSAuditEvent", "STSWSGIApp", "StaticServiceAuthenticator", "sign_assertion",
]
