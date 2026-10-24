"""Tests for password hashing and JWT tokens."""

from __future__ import annotations

import time

import pytest

from app.core.security import (
    AuthError,
    TokenClaims,
    create_access_token,
    decode_access_token,
    generate_api_secret,
    hash_password,
    verify_password,
)

_SECRET = "unit-test-secret-key-0123456789-abcdef"


def test_password_roundtrip() -> None:
    stored = hash_password("S3cret!")
    assert stored.startswith("scrypt$")
    assert verify_password("S3cret!", stored)
    assert not verify_password("wrong", stored)


def test_password_salt_is_random() -> None:
    assert hash_password("x") != hash_password("x")


def test_password_empty_rejected() -> None:
    with pytest.raises(AuthError):
        hash_password("")


def test_verify_malformed_hash() -> None:
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("", "")


def test_jwt_roundtrip() -> None:
    token = create_access_token(
        TokenClaims(subject="ali", role="AGENT", agency_id="local"),
        secret=_SECRET,
        expires_minutes=60,
    )
    claims = decode_access_token(token, secret=_SECRET)
    assert claims["sub"] == "ali"
    assert claims["role"] == "AGENT"
    assert claims["agency_id"] == "local"


def test_jwt_expired() -> None:
    token = create_access_token(
        TokenClaims(subject="ali"),
        secret=_SECRET,
        expires_minutes=1,
        now=int(time.time()) - 3600,
    )
    with pytest.raises(AuthError):
        decode_access_token(token, secret=_SECRET)


def test_jwt_wrong_secret() -> None:
    token = create_access_token(TokenClaims(subject="ali"), secret=_SECRET, expires_minutes=60)
    with pytest.raises(AuthError):
        decode_access_token(token, secret=_SECRET + "-different")


def test_generate_api_secret_is_unique() -> None:
    assert generate_api_secret() != generate_api_secret()
