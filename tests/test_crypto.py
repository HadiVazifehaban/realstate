"""Tests for the local PII encryption layer."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from app.core.crypto import CryptoError, PiiCipher


def test_encrypt_decrypt_roundtrip(cipher: PiiCipher) -> None:
    plaintext = "علی رضایی - ۰۹۱۲۳۴۵۶۷۸۹"
    token = cipher.encrypt(plaintext)
    assert token is not None
    assert token != plaintext
    assert cipher.decrypt(token) == plaintext


def test_none_passthrough(cipher: PiiCipher) -> None:
    assert cipher.encrypt(None) is None
    assert cipher.decrypt(None) is None


def test_ciphertext_is_nondeterministic(cipher: PiiCipher) -> None:
    # Fernet embeds a random IV -> same plaintext yields different tokens.
    assert cipher.encrypt("same") != cipher.encrypt("same")


def test_decrypt_with_wrong_key_fails(cipher: PiiCipher) -> None:
    token = cipher.encrypt("secret")
    other = PiiCipher(PiiCipher.generate_key())
    with pytest.raises(CryptoError):
        other.decrypt(token)


def test_invalid_key_rejected() -> None:
    with pytest.raises(CryptoError):
        PiiCipher(b"not-a-valid-fernet-key")


def test_encrypt_many(cipher: PiiCipher) -> None:
    result = cipher.encrypt_many(owner_name="حسین", owner_phone="09120000000")
    assert set(result) == {"owner_name", "owner_phone"}
    assert cipher.decrypt(result["owner_name"]) == "حسین"


def test_blind_index_is_deterministic_and_normalised(cipher: PiiCipher) -> None:
    a = cipher.blind_index("0912 345 6789")
    b = cipher.blind_index("0912-345-6789")
    c = cipher.blind_index("09123456789")
    assert a == b == c  # formatting differences collapse to one index
    assert a != cipher.blind_index("09999999999")


def test_blind_index_none(cipher: PiiCipher) -> None:
    assert cipher.blind_index(None) is None


def test_from_key_file_creates_secure_file(temp_key_file: Path) -> None:
    cipher = PiiCipher.from_key_file(temp_key_file)
    assert temp_key_file.exists()
    # Reload yields a working cipher with the same key.
    reloaded = PiiCipher.from_key_file(temp_key_file)
    assert reloaded.decrypt(cipher.encrypt("x")) == "x"
    mode = stat.S_IMODE(temp_key_file.stat().st_mode)
    assert mode & 0o077 == 0  # not world/group accessible


def test_key_file_content_matches_reloaded_cipher(temp_key_file: Path) -> None:
    original = PiiCipher.from_key_file(temp_key_file)
    key_bytes = temp_key_file.read_bytes().strip()
    same = PiiCipher(key_bytes)
    token = original.encrypt("hello")
    assert same.decrypt(token) == "hello"
