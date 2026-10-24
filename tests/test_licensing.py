"""Tests for hardware fingerprinting and the licensed state machine."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.core.licensing import (
    RSA_KEY_SIZE,
    HardwareFingerprint,
    InvalidSignatureError,
    LicenseManager,
    LicensePayload,
    LicenseStatus,
    decode_license,
    encode_license,
    evaluate_license,
    generate_keypair,
)

# Use a smaller key in tests for speed; production default is asserted separately.
PUBLIC_PEM, PRIVATE_PEM = None, None


@pytest.fixture(scope="module")
def keypair():
    private_pem, public_pem = generate_keypair(key_size=2048)
    return private_pem, public_pem


@pytest.fixture()
def payload() -> LicensePayload:
    now = int(time.time())
    return LicensePayload(
        license_id="AVG-TEST-1",
        agency_name="املاک آفتاب",
        machine_fingerprint_hash="abc123",
        max_concurrent_users=8,
        issued_at=now,
        expires_at=now + 365 * 86400,
        features=["MLS", "PDF"],
    )


def test_default_key_size_is_4096() -> None:
    assert RSA_KEY_SIZE == 4096


def test_fingerprint_hash_is_deterministic() -> None:
    fp = HardwareFingerprint(cpu_id="CPU-X", mac_address="aa:bb:cc:dd:ee:ff")
    assert fp.hash() == fp.hash()
    assert fp.component_count == 2


def test_fingerprint_empty_raises() -> None:
    with pytest.raises(Exception):
        HardwareFingerprint().hash()


def test_encode_decode_roundtrip(payload, keypair) -> None:
    private_pem, public_pem = keypair
    token = encode_license(payload, private_pem)
    assert token.startswith("AVG1.")
    decoded = decode_license(token, public_pem)
    assert decoded.license_id == payload.license_id
    assert decoded.agency_name == payload.agency_name
    assert decoded.max_concurrent_users == payload.max_concurrent_users
    assert decoded.features == ["MLS", "PDF"]


def test_tampered_token_rejected(payload, keypair) -> None:
    private_pem, public_pem = keypair
    token = encode_license(payload, private_pem)
    _, body, sig = token.split(".")
    tampered = f"AVG1.{body[:-2]}XY.{sig}"
    with pytest.raises(Exception):
        decode_license(tampered, public_pem)


def test_wrong_public_key_rejected(payload, keypair) -> None:
    private_pem, _ = keypair
    _, other_public = generate_keypair(key_size=2048)
    token = encode_license(payload, private_pem)
    with pytest.raises(InvalidSignatureError):
        decode_license(token, other_public)


def test_evaluate_not_installed() -> None:
    result = evaluate_license(None, "abc123")
    assert result.status is LicenseStatus.NOT_INSTALLED
    assert not result.is_usable


def test_evaluate_hardware_mismatch(payload) -> None:
    result = evaluate_license(payload, "different-hash")
    assert result.status is LicenseStatus.LOCKED_HARDWARE_MISMATCH
    assert not result.is_usable


def test_evaluate_expired(payload) -> None:
    payload.expires_at = int(time.time()) - 10
    result = evaluate_license(payload, payload.machine_fingerprint_hash)
    assert result.status is LicenseStatus.EXPIRED


def test_evaluate_active_with_recent_heartbeat(payload) -> None:
    now = int(time.time())
    result = evaluate_license(
        payload, payload.machine_fingerprint_hash, now=now, last_heartbeat_at=now
    )
    assert result.status is LicenseStatus.ACTIVE
    assert result.is_usable
    assert result.offline_grace_deadline == now + 14 * 86400


def test_evaluate_grace_period_when_never_heartbeated(payload) -> None:
    now = int(time.time())
    result = evaluate_license(
        payload, payload.machine_fingerprint_hash, now=now, starts_from=now
    )
    assert result.status is LicenseStatus.GRACE_PERIOD
    assert result.is_usable


def test_evaluate_offline_grace_expired(payload) -> None:
    now = int(time.time())
    old_heartbeat = now - 20 * 86400  # 20 days without internet
    result = evaluate_license(
        payload,
        payload.machine_fingerprint_hash,
        now=now,
        last_heartbeat_at=old_heartbeat,
        grace_days=14,
    )
    assert result.status is LicenseStatus.OFFLINE_GRACE_EXPIRED
    assert not result.is_usable


def test_license_manager_end_to_end(tmp_path: Path, payload, keypair) -> None:
    private_pem, public_pem = keypair
    license_file = tmp_path / "node.lic"
    public_file = tmp_path / "license_public.pem"
    public_file.write_bytes(public_pem)

    manager = LicenseManager(
        license_file=license_file,
        public_key_file=public_file,
        grace_days=14,
        fingerprint_override="dev-machine",
    )
    # No token yet.
    assert manager.evaluate().status is LicenseStatus.NOT_INSTALLED

    # Bind license to THIS (overridden) fingerprint.
    payload.machine_fingerprint_hash = manager.machine_fingerprint_hash()
    manager.write_token(encode_license(payload, private_pem))

    evaluation = manager.evaluate()
    assert evaluation.status is LicenseStatus.GRACE_PERIOD
    assert evaluation.payload is not None


def test_license_manager_invalid_signature(tmp_path: Path, payload, keypair) -> None:
    private_pem, _ = keypair
    _, other_public = generate_keypair(key_size=2048)
    license_file = tmp_path / "node.lic"
    public_file = tmp_path / "license_public.pem"
    public_file.write_bytes(other_public)
    license_file.write_text(encode_license(payload, private_pem), encoding="utf-8")

    manager = LicenseManager(
        license_file=license_file,
        public_key_file=public_file,
        fingerprint_override="dev-machine",
    )
    assert manager.evaluate().status is LicenseStatus.INVALID_SIGNATURE
