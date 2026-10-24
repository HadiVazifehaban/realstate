"""Commercial licensing: hardware binding + offline grace + RSA-4096 signatures.

Design
------
The AVG licensing model protects the on-premise node:

1. A **hardware fingerprint** is derived from the physical machine
   (motherboard serial, CPU identity, primary MAC, machine-id).
2. The central AVG *license server* signs a compact token with its **RSA-4096
   private key**; the token embeds the fingerprint hash, the agency name, the
   concurrent-user cap and the expiry date.
3. The client verifies the token purely **offline** against the embedded
   **public key** -- no network round-trip is required to boot the office.
4. A heartbeat to the hub refreshes ``last_heartbeat_at``; when the internet
   dies the node keeps working until ``last_heartbeat_at + grace_days``
   (default 14 days) after which it enters the offline-lock state.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

# ---------------------------------------------------------------------------
#  Constants & errors
# ---------------------------------------------------------------------------
TOKEN_PREFIX = "AVG1"
RSA_KEY_SIZE = 4096
_DEFAULT_GRACE_DAYS = 14


class LicenseStatus(str, Enum):
    """Operational status of the installed commercial license."""

    ACTIVE = "ACTIVE"
    GRACE_PERIOD = "GRACE_PERIOD"
    OFFLINE_GRACE_EXPIRED = "OFFLINE_GRACE_EXPIRED"
    EXPIRED = "EXPIRED"
    LOCKED_HARDWARE_MISMATCH = "LOCKED_HARDWARE_MISMATCH"
    NOT_INSTALLED = "NOT_INSTALLED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"


class LicenseError(RuntimeError):
    """Base class for licensing failures."""


class LicenseFormatError(LicenseError):
    """The token string is malformed or unreadable."""


class InvalidSignatureError(LicenseError):
    """The token signature does not match the trusted public key."""


# ---------------------------------------------------------------------------
#  Hardware fingerprint
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HardwareFingerprint:
    """Stable physical identity of the machine running the office node."""

    cpu_id: str = ""
    motherboard_serial: str = ""
    mac_address: str = ""
    machine_id: str = ""

    def canonical(self) -> str:
        """Deterministic string representation used as hash input."""
        return "|".join(
            f"{name}={value.strip().lower()}"
            for name, value in (
                ("cpu", self.cpu_id),
                ("board", self.motherboard_serial),
                ("mac", self.mac_address),
                ("mid", self.machine_id),
            )
            if value and value.strip()
        )

    def hash(self) -> str:
        """SHA-256 hex digest that is stored in the signed license token."""
        if not self.canonical():
            raise LicenseError("Unable to derive a hardware fingerprint from this machine.")
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()

    @property
    def component_count(self) -> int:
        return sum(
            1
            for value in (
                self.cpu_id,
                self.motherboard_serial,
                self.mac_address,
                self.machine_id,
            )
            if value and value.strip()
        )


def _read_first_line(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore").strip().splitlines()[0]
    except (OSError, IndexError):
        return ""


def _safe_cpu_count() -> int:
    return os.cpu_count() or 0


def _collect_cpu_id() -> str:
    text = ""
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    for key in ("Serial", "model name", "Hardware"):
        match = re.search(rf"^{re.escape(key)}\s*:\s*(.+)$", text, re.MULTILINE)
        if match and match.group(1).strip():
            return f"{match.group(1).strip()};cores={_safe_cpu_count()}"
    return f"{platform.processor()};cores={_safe_cpu_count()}"


def _collect_motherboard_serial() -> str:
    for candidate in (
        "/sys/class/dmi/id/board_serial",
        "/sys/class/dmi/id/product_uuid",
        "/sys/class/dmi/id/product_serial",
    ):
        value = _read_first_line(candidate)
        if value:
            return value
    return ""


def _collect_mac_address() -> str:
    node = uuid.getnode()
    if (node >> 40) & 0x01:  # multicast bit => no real MAC available
        return ""
    parts = [(node >> (8 * (5 - i))) & 0xFF for i in range(6)]
    return ":".join(f"{p:02x}" for p in parts)


def _collect_machine_id() -> str:
    for candidate in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        value = _read_first_line(candidate)
        if value:
            return value
    return ""


def collect_hardware_fingerprint(override: str | None = None) -> HardwareFingerprint:
    """Collect the machine fingerprint.

    ``override`` (from ``MACHINE_FINGERPRINT_OVERRIDE``) is honoured for
    deterministic development/testing; it must never be set in production.
    """
    if override:
        return HardwareFingerprint(cpu_id=f"override:{override}")
    return HardwareFingerprint(
        cpu_id=_collect_cpu_id(),
        motherboard_serial=_collect_motherboard_serial(),
        mac_address=_collect_mac_address(),
        machine_id=_collect_machine_id(),
    )


# ---------------------------------------------------------------------------
#  Key material
# ---------------------------------------------------------------------------
def generate_keypair(key_size: int = RSA_KEY_SIZE) -> tuple[bytes, bytes]:
    """Generate an ``(private_pem, public_pem)`` RSA key pair."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def load_public_key(public_pem: bytes):
    return serialization.load_pem_public_key(public_pem)


def load_private_key(private_pem: bytes):
    return serialization.load_pem_private_key(private_pem, password=None)


# ---------------------------------------------------------------------------
#  License payload & token codec
# ---------------------------------------------------------------------------
@dataclass
class LicensePayload:
    """The signed content of a commercial license token."""

    license_id: str
    agency_name: str
    machine_fingerprint_hash: str
    max_concurrent_users: int
    issued_at: int
    expires_at: int
    features: list[str] = field(default_factory=list)
    version: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LicensePayload":
        required = {
            "license_id",
            "agency_name",
            "machine_fingerprint_hash",
            "max_concurrent_users",
            "issued_at",
            "expires_at",
        }
        missing = required - data.keys()
        if missing:
            raise LicenseFormatError(f"License payload missing fields: {sorted(missing)}")
        return cls(
            license_id=str(data["license_id"]),
            agency_name=str(data["agency_name"]),
            machine_fingerprint_hash=str(data["machine_fingerprint_hash"]),
            max_concurrent_users=int(data["max_concurrent_users"]),
            issued_at=int(data["issued_at"]),
            expires_at=int(data["expires_at"]),
            features=list(data.get("features") or []),
            version=int(data.get("version", 1)),
        )

    @property
    def expires_at_dt(self):
        from datetime import datetime, timezone

        return datetime.fromtimestamp(self.expires_at, tz=timezone.utc)


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def encode_license(payload: LicensePayload, private_pem: bytes) -> str:
    """Sign ``payload`` and return a compact ``AVG1.<payload>.<sig>`` token."""
    body = json.dumps(
        payload.to_dict(), separators=(",", ":"), ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    private_key = load_private_key(private_pem)
    signature = private_key.sign(
        body,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )
    return f"{TOKEN_PREFIX}.{_b64e(body)}.{_b64e(signature)}"


def decode_license(token: str, public_pem: bytes, *, verify: bool = True) -> LicensePayload:
    """Decode (and by default verify) a license token."""
    if not token or not token.strip():
        raise LicenseFormatError("Empty license token")
    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
        raise LicenseFormatError("Unrecognised license token format")
    try:
        body = _b64d(parts[1])
        signature = _b64d(parts[2])
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise LicenseFormatError(f"Malformed license token: {exc}") from exc

    if verify:
        public_key = load_public_key(public_pem)
        try:
            public_key.verify(
                signature,
                body,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256(),
            )
        except InvalidSignature as exc:
            raise InvalidSignatureError("License signature verification failed") from exc

    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise LicenseFormatError(f"License payload is not valid JSON: {exc}") from exc
    return LicensePayload.from_dict(data)


# ---------------------------------------------------------------------------
#  Evaluation state machine
# ---------------------------------------------------------------------------
@dataclass
class LicenseEvaluation:
    """Result of evaluating a license against the current machine and clock."""

    status: LicenseStatus
    payload: LicensePayload | None = None
    reason: str = ""
    offline_grace_deadline: int | None = None  # unix timestamp

    @property
    def is_usable(self) -> bool:
        return self.status in (LicenseStatus.ACTIVE, LicenseStatus.GRACE_PERIOD)


def evaluate_license(
    payload: LicensePayload | None,
    machine_fingerprint_hash: str,
    *,
    now: int | None = None,
    last_heartbeat_at: int | None = None,
    grace_days: int = _DEFAULT_GRACE_DAYS,
    starts_from: int | None = None,
) -> LicenseEvaluation:
    """Pure (side-effect free) license state machine.

    Parameters
    ----------
    payload:
        Decoded, signature-verified license payload, or ``None`` if missing.
    machine_fingerprint_hash:
        Hash of the *current* machine, computed via
        :meth:`HardwareFingerprint.hash`.
    now:
        Current unix timestamp (injectable for tests).
    last_heartbeat_at:
        Unix timestamp of the last successful hub heartbeat (``None`` if the
        node never contacted the hub).
    grace_days:
        Length of the offline grace window.
    starts_from:
        Fallback anchor for the grace window when no heartbeat exists yet.
    """
    now = int(now if now is not None else time.time())

    # 1) Missing license.
    if payload is None:
        return LicenseEvaluation(LicenseStatus.NOT_INSTALLED, reason="No license installed")

    # 2) Hardware binding -- highest priority.
    if payload.machine_fingerprint_hash != machine_fingerprint_hash:
        return LicenseEvaluation(
            LicenseStatus.LOCKED_HARDWARE_MISMATCH,
            payload=payload,
            reason="Hardware fingerprint does not match the issued license",
        )

    # 3) Absolute license expiry.
    if now > payload.expires_at:
        return LicenseEvaluation(
            LicenseStatus.EXPIRED,
            payload=payload,
            reason="License subscription has expired",
        )

    # 4) Offline grace -- measured from the last successful heartbeat.
    anchor = last_heartbeat_at if last_heartbeat_at is not None else starts_from
    anchor = anchor if anchor is not None else payload.issued_at
    deadline = anchor + grace_days * 86400

    if last_heartbeat_at is None:
        status = (
            LicenseStatus.GRACE_PERIOD
            if now <= deadline
            else LicenseStatus.OFFLINE_GRACE_EXPIRED
        )
        return LicenseEvaluation(
            status,
            payload=payload,
            reason="Node has not contacted the license hub yet",
            offline_grace_deadline=deadline,
        )

    if now > deadline:
        return LicenseEvaluation(
            LicenseStatus.OFFLINE_GRACE_EXPIRED,
            payload=payload,
            reason=f"Offline grace period ({grace_days}d) exceeded",
            offline_grace_deadline=deadline,
        )

    return LicenseEvaluation(
        LicenseStatus.ACTIVE,
        payload=payload,
        reason="License valid and recently heartbeated",
        offline_grace_deadline=deadline,
    )


# ---------------------------------------------------------------------------
#  File-backed manager (token on disk, public key embedded)
# ---------------------------------------------------------------------------
class LicenseManager:
    """Loads the node license token from disk and evaluates it offline."""

    def __init__(
        self,
        *,
        license_file: Path,
        public_key_file: Path,
        grace_days: int = _DEFAULT_GRACE_DAYS,
        fingerprint_override: str | None = None,
    ) -> None:
        self.license_file = Path(license_file)
        self.public_key_file = Path(public_key_file)
        self.grace_days = grace_days
        self._fingerprint_override = fingerprint_override or None
        self._cached_token: str | None = None

    # ------------------------------------------------------------------ loading
    def read_token(self) -> str | None:
        if self._cached_token is not None:
            return self._cached_token
        if not self.license_file.exists():
            return None
        self._cached_token = self.license_file.read_text(encoding="utf-8").strip() or None
        return self._cached_token

    def read_public_key(self) -> bytes | None:
        if not self.public_key_file.exists():
            return None
        return self.public_key_file.read_bytes()

    def write_token(self, token: str) -> None:
        self.license_file.parent.mkdir(parents=True, exist_ok=True)
        self.license_file.write_text(token.strip(), encoding="utf-8")
        try:
            os.chmod(self.license_file, 0o600)
        except OSError:  # pragma: no cover - platform dependent
            pass
        self._cached_token = token.strip()

    # ------------------------------------------------------------------ helpers
    def machine_fingerprint(self) -> HardwareFingerprint:
        return collect_hardware_fingerprint(self._fingerprint_override)

    def machine_fingerprint_hash(self) -> str:
        return self.machine_fingerprint().hash()

    def load_payload(self) -> LicensePayload | None:
        """Read + verify the on-disk token, returning ``None`` when absent."""
        token = self.read_token()
        if not token:
            return None
        public_key = self.read_public_key()
        if public_key is None:
            raise LicenseError("Trusted license public key is missing")
        return decode_license(token, public_key)

    # ---------------------------------------------------------------- evaluate
    def evaluate(
        self,
        *,
        now: int | None = None,
        last_heartbeat_at: int | None = None,
        starts_from: int | None = None,
    ) -> LicenseEvaluation:
        """Full offline evaluation, degrading gracefully on bad tokens."""
        try:
            fingerprint_hash = self.machine_fingerprint_hash()
        except LicenseError as exc:
            return LicenseEvaluation(LicenseStatus.NOT_INSTALLED, reason=str(exc))
        try:
            payload = self.load_payload()
        except InvalidSignatureError as exc:
            return LicenseEvaluation(LicenseStatus.INVALID_SIGNATURE, reason=str(exc))
        except (LicenseFormatError, LicenseError) as exc:
            return LicenseEvaluation(LicenseStatus.INVALID_SIGNATURE, reason=str(exc))

        return evaluate_license(
            payload,
            fingerprint_hash,
            now=now,
            last_heartbeat_at=last_heartbeat_at,
            grace_days=self.grace_days,
            starts_from=starts_from,
        )
