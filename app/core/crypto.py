"""Local PII encryption layer ("Zero-Trust" owner vault).

Sensitive owner data (names, phones, exact addresses, pelak/unit numbers) is
encrypted with ``cryptography.Fernet`` symmetric AEAD before it ever touches
the database.  Each agency node owns a unique key that never leaves the
on-premise machine.

Two primitives are provided:

* :meth:`PiiCipher.encrypt` / :meth:`PiiCipher.decrypt` -- reversible
  authenticated encryption for display.
* :meth:`PiiCipher.blind_index` -- deterministic HMAC-SHA256 digest used to
  *search* encrypted columns (e.g. "find owner by phone") without ever
  decrypting the whole table.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import stat
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class CryptoError(RuntimeError):
    """Raised when encryption/decryption cannot proceed."""


class PiiCipher:
    """Symmetric cipher dedicated to a single agency node."""

    def __init__(self, key: bytes) -> None:
        if not key:
            raise CryptoError("PII encryption key must not be empty")
        try:
            self._fernet = Fernet(key)
        except (ValueError, TypeError) as exc:  # invalid key material
            raise CryptoError(f"Invalid Fernet key: {exc}") from exc
        # Derive a separate, purpose-bound key for blind indexes so it can never
        # be confused with the encryption key.
        self._index_key = hashlib.sha256(b"avg-pii-blind-index:" + key).digest()

    # ------------------------------------------------------------- key handling
    @staticmethod
    def generate_key() -> bytes:
        """Create a fresh, URL-safe base64 Fernet key."""
        return Fernet.generate_key()

    @classmethod
    def from_key_file(cls, key_file: Path) -> "PiiCipher":
        """Load an existing key file or create one with ``0600`` permissions."""
        key_file = Path(key_file)
        if key_file.exists():
            key = key_file.read_bytes().strip()
            return cls(key)
        key = cls.generate_key()
        _write_secret_file(key_file, key)
        return cls(key)

    @classmethod
    def from_env(cls) -> "PiiCipher":
        """Build a cipher from the ``AVG_PII_KEY`` environment variable."""
        raw = os.environ.get("AVG_PII_KEY", "").strip()
        if not raw:
            raise CryptoError("AVG_PII_KEY environment variable is not set")
        return cls(raw.encode("utf-8"))

    # ------------------------------------------------------------------ crypto
    def encrypt(self, value: str | None) -> str | None:
        """Encrypt ``value``; ``None`` passes through unchanged."""
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str | None) -> str | None:
        """Decrypt a token produced by :meth:`encrypt`."""
        if token is None:
            return None
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise CryptoError("PII token could not be decrypted (wrong key?)") from exc

    def encrypt_many(self, **fields: str | None) -> dict[str, str | None]:
        """Encrypt several named fields at once."""
        return {name: self.encrypt(val) for name, val in fields.items()}

    def blind_index(self, value: str | None, *, normalize: bool = True) -> str | None:
        """Deterministic, non-reversible index for exact-match lookups.

        ``normalize`` strips spaces/dashes and applies ``casefold`` which is the
        right behaviour for phone numbers and human names (Persian included).
        """
        if value is None:
            return None
        material = value
        if normalize:
            material = "".join(value.split()).replace("-", "")
            material = material.casefold()
        digest = hmac.new(self._index_key, material.encode("utf-8"), hashlib.sha256)
        return base64.urlsafe_b64encode(digest.digest()).decode("ascii")


def _write_secret_file(path: Path, content: bytes) -> None:
    """Atomically write ``content`` to ``path`` with owner-only permissions."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    try:
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:  # pragma: no cover - platform dependent
        pass
    tmp.replace(path)
