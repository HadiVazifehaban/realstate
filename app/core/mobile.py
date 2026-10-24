"""Iran mobile normalization to E.164.

The fast/professional funnels accept whatever the user typed on a Persian
keyboard -- Persian digits (۰۱۲...), Arabic-Indic digits (٠١٢...), spaces,
dashes, ``09...``, ``+989...`` or ``00989...`` -- and every layer (OTP
store, Keycloak ``phone`` attribute, audit) keys on one canonical form:
``+989123456789``.

Normalization is intentionally strict: anything that is not an Iranian
mobile (``+989`` + 9 digits, third digit ``9``) raises :class:`MobileError`
so both the Pydantic schemas and the service layer reject it with the same
Persian message.
"""

from __future__ import annotations

import re

# Persian digits U+06F0..U+06F9, Arabic-Indic U+0660..U+0669.
_FA_DIGITS = {chr(0x06F0 + i): str(i) for i in range(10)}
_AR_DIGITS = {chr(0x0660 + i): str(i) for i in range(10)}
_DIGIT_MAP = {**_FA_DIGITS, **_AR_DIGITS}

_VALID_E164 = re.compile(r"^\+989\d{9}$")


class MobileError(ValueError):
    """Raised when a raw input is not a valid Iranian mobile number."""


def to_latin_digits(raw: str) -> str:
    """Fold Persian/Arabic-Indic digits to ASCII; leave the rest untouched."""
    return "".join(_DIGIT_MAP.get(ch, ch) for ch in raw)


def normalize_mobile(raw: str | None) -> str:
    """Normalize an Iranian mobile to E.164 (``+989xxxxxxxxx``).

    Raises :class:`MobileError` for anything else (empty, landline,
    foreign numbers, wrong length).
    """
    if raw is None:
        raise MobileError("شماره موبایل معتبر وارد کنید.")
    text = to_latin_digits(raw).strip()
    # Tolerate common separators users paste from contacts.
    text = re.sub(r"[\s\-().]+", "", text)
    if text.startswith("0098"):
        text = "+98" + text[4:]
    elif text.startswith("98") and len(text) == 12:
        text = "+" + text
    elif text.startswith("0"):
        text = "+98" + text[1:]
    elif text.startswith("9") and len(text) == 10:
        text = "+98" + text
    if not _VALID_E164.match(text):
        raise MobileError("شماره موبایل معتبر وارد کنید.")
    return text


def mask_mobile(e164: str) -> str:
    """Privacy-safe display form: ``+98912•••4567`` (never logs the full number)."""
    if len(e164) >= 8:
        return e164[:6] + "•••" + e164[-4:]
    return "•••"


__all__ = ["MobileError", "mask_mobile", "normalize_mobile", "to_latin_digits"]
