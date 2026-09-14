"""Signed Aquila assertion support for the STS conformance fixture."""

from __future__ import annotations

import base64
import json
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


class AssertionVerificationError(ValueError):
    """Raised without exposing a signed assertion or signature."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise AssertionVerificationError("invalid compact assertion")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, UnicodeEncodeError) as exc:
        raise AssertionVerificationError("invalid compact assertion") from exc


def sign_assertion(claims: Mapping[str, Any], private_key: Ed25519PrivateKey, *, key_id: str) -> str:
    """Create a compact EdDSA JWS for deterministic integration fixtures."""
    header = {"alg": "EdDSA", "kid": key_id, "typ": "JWT"}
    encoded_header = _encode(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    encoded_claims = _encode(json.dumps(dict(claims), sort_keys=True, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    return f"{signing_input.decode('ascii')}.{_encode(private_key.sign(signing_input))}"


class Ed25519AssertionVerifier:
    """Verify a compact Aquila assertion against an explicit key set."""

    def __init__(self, verification_keys: Mapping[str, Ed25519PublicKey]) -> None:
        self._verification_keys = dict(verification_keys)

    def verify(self, compact_assertion: str) -> dict[str, Any]:
        parts = compact_assertion.split(".") if isinstance(compact_assertion, str) else []
        if len(parts) != 3:
            raise AssertionVerificationError("invalid compact assertion")
        encoded_header, encoded_claims, encoded_signature = parts
        try:
            header = json.loads(_decode(encoded_header))
            claims = json.loads(_decode(encoded_claims))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AssertionVerificationError("invalid compact assertion") from exc
        if (
            not isinstance(header, dict)
            or header.get("alg") != "EdDSA"
            or not isinstance(header.get("kid"), str)
            or not isinstance(claims, dict)
        ):
            raise AssertionVerificationError("invalid assertion header")
        key = self._verification_keys.get(header["kid"])
        if key is None:
            raise AssertionVerificationError("unknown assertion signing key")
        try:
            key.verify(_decode(encoded_signature), f"{encoded_header}.{encoded_claims}".encode("ascii"))
        except InvalidSignature as exc:
            raise AssertionVerificationError("invalid assertion signature") from exc
        return claims
