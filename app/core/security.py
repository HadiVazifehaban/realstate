"""Authentication helpers: password hashing and short-lived JWT tokens.

Uses only the standard library (``hashlib.scrypt``) for password hashing so the
on-premise node has zero extra runtime dependencies, plus ``PyJWT`` for tokens.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any

import jwt

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_HASH_BYTES = 32


class AuthError(RuntimeError):
    """Raised when a credential or token is invalid."""


# ---------------------------------------------------------------------------
#  Passwords
# ---------------------------------------------------------------------------
def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Hash ``password`` with scrypt; returns ``scrypt$<salt>$<hash>`` (base64)."""
    if not password:
        raise AuthError("Password must not be empty")
    salt = salt or os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_HASH_BYTES,
    )
    return "scrypt${}${}".format(
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(derived).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of ``password`` against a stored hash."""
    if not password or not stored:
        return False
    try:
        scheme, salt_b64, hash_b64 = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, base64.binascii.Error):  # type: ignore[attr-defined]
        return False
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=len(expected),
    )
    return hmac.compare_digest(derived, expected)


def generate_api_secret(length: int = 32) -> str:
    """Return a URL-safe random secret (used for node<->hub sync tokens)."""
    return secrets.token_urlsafe(length)


# ---------------------------------------------------------------------------
#  JWT
# ---------------------------------------------------------------------------
@dataclass
class TokenClaims:
    subject: str
    role: str = "AGENT"
    agency_id: str | None = None
    extra: dict[str, Any] | None = None


def create_access_token(
    claims: TokenClaims,
    *,
    secret: str,
    algorithm: str = "HS256",
    expires_minutes: int = 720,
    now: int | None = None,
) -> str:
    """Create a signed JWT access token for an agency user."""
    issued = int(now if now is not None else time.time())
    payload: dict[str, Any] = {
        "sub": claims.subject,
        "role": claims.role,
        "iat": issued,
        "exp": issued + expires_minutes * 60,
    }
    if claims.agency_id:
        payload["agency_id"] = claims.agency_id
    if claims.extra:
        payload.update(claims.extra)
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(
    token: str, *, secret: str, algorithm: str = "HS256"
) -> dict[str, Any]:
    """Verify and decode a JWT, raising :class:`AuthError` on failure."""
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc
