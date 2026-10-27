"""Encrypted database-backed Zibal credentials and safe public status."""

from __future__ import annotations

from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings
from app.models.billing import ZibalGatewayConfiguration
from app.services.zibal import ZibalNotConfigured, validate_zibal_web_urls


def _fernet(settings: Settings) -> Fernet:
    key = settings.zibal_credential_encryption_key.strip()
    if not key:
        raise ZibalNotConfigured("کلید رمزگذاری تنظیمات زیبال روی سرور تنظیم نشده است.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ZibalNotConfigured("کلید رمزگذاری تنظیمات زیبال معتبر نیست.") from exc


def _decrypt_merchant(row: ZibalGatewayConfiguration, settings: Settings) -> str:
    if not row.merchant_ciphertext:
        return ""
    try:
        return _fernet(settings).decrypt(row.merchant_ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exc:
        raise ZibalNotConfigured("اعتبارنامهٔ ذخیره‌شدهٔ زیبال قابل رمزگشایی نیست.") from exc


async def load_zibal_settings(session: AsyncSession, settings: Settings) -> Settings:
    """Use encrypted DB configuration when present; otherwise retain env fallback."""
    row = await session.get(ZibalGatewayConfiguration, 1)
    if row is None:
        return settings
    merchant = _decrypt_merchant(row, settings)
    return settings.model_copy(update={
        "zibal_enabled": row.enabled,
        "zibal_test_mode": row.test_mode,
        "zibal_merchant": merchant,
        "zibal_callback_url": row.callback_url,
        "zibal_result_url": row.result_url,
    })


async def public_zibal_settings(session: AsyncSession, settings: Settings) -> dict:
    row = await session.get(ZibalGatewayConfiguration, 1)
    if row is None:
        merchant = settings.zibal_merchant.strip()
        callback_url = settings.zibal_callback_url
        result_url = settings.zibal_result_url
        enabled = settings.zibal_enabled
        test_mode = settings.zibal_test_mode
        configured = bool(merchant)
        source = "environment"
        last4 = merchant[-4:] if merchant else ""
        version = 0
    else:
        configured = bool(row.merchant_ciphertext)
        source = "database"
        last4 = row.merchant_last4 if configured else ""
        callback_url = row.callback_url
        result_url = row.result_url
        enabled = row.enabled
        test_mode = row.test_mode
        version = row.version
    return {
        "enabled": enabled,
        "test_mode": test_mode,
        "merchant_configured": configured,
        "merchant_masked": f"••••{last4}" if last4 else None,
        "source": source,
        "encryption_key_ready": bool(settings.zibal_credential_encryption_key.strip()),
        "callback_url": callback_url,
        "result_url": result_url,
        "request_url": settings.zibal_request_url,
        "verify_url": settings.zibal_verify_url,
        "inquiry_url": settings.zibal_inquiry_url,
        "start_url": settings.zibal_start_url,
        "version": version,
    }


async def save_zibal_settings(
    session: AsyncSession,
    *,
    settings: Settings,
    actor: str,
    enabled: bool,
    test_mode: bool,
    callback_url: str,
    result_url: str,
    expected_version: int,
    merchant_code: str | None,
    clear_merchant: bool,
) -> ZibalGatewayConfiguration:
    callback_url = callback_url.strip()
    result_url = result_url.strip()
    validate_zibal_web_urls(settings, callback_url=callback_url, result_url=result_url)
    if clear_merchant and merchant_code:
        raise ValueError("هم‌زمان نمی‌توان اعتبارنامه را پاک و جایگزین کرد.")
    if merchant_code is not None:
        merchant_code = merchant_code.strip()
        if not merchant_code or len(merchant_code) > 512 or any(ord(ch) < 32 for ch in merchant_code):
            raise ValueError("کد مرچنت معتبر نیست.")

    row = (await session.exec(
        select(ZibalGatewayConfiguration)
        .where(ZibalGatewayConfiguration.id == 1)
        .with_for_update()
    )).first()
    current_version = row.version if row else 0
    if expected_version != current_version:
        raise RuntimeError("تنظیمات زیبال هم‌زمان تغییر کرده است؛ صفحه را تازه‌سازی کنید.")

    current_ciphertext = row.merchant_ciphertext if row else None
    current_last4 = row.merchant_last4 if row else ""
    if clear_merchant:
        if enabled:
            raise ValueError("تا وقتی کد مرچنت پاک است، درگاه نمی‌تواند فعال باشد.")
        ciphertext = None
        last4 = ""
    elif merchant_code is not None:
        cipher = _fernet(settings)
        ciphertext = cipher.encrypt(merchant_code.encode("utf-8")).decode("ascii")
        last4 = merchant_code[-4:]
    elif row and current_ciphertext:
        # Configuration edits that do not touch the credential can proceed
        # without decrypting it. Enabling still requires a working key/merchant.
        ciphertext = current_ciphertext
        last4 = current_last4
        if enabled and not _decrypt_merchant(row, settings):
            raise ValueError("برای فعال‌سازی زیبال، کد مرچنت لازم است.")
    else:
        # Migrating an env-configured credential into the DB requires the
        # dedicated encryption key; never silently discard or store it in clear.
        new_merchant = settings.zibal_merchant.strip() if row is None else ""
        if enabled and not new_merchant:
            raise ValueError("برای فعال‌سازی زیبال، کد مرچنت لازم است.")
        if new_merchant:
            cipher = _fernet(settings)
            ciphertext = cipher.encrypt(new_merchant.encode("utf-8")).decode("ascii")
            last4 = new_merchant[-4:]
        else:
            ciphertext = None
            last4 = ""

    # Validate that the requested enabled config is operational before saving;
    # the gateway remains in test mode unless an explicit later update changes it.
    if enabled:
        from app.services.zibal import ZibalPaymentProvider

        merchant = (
            merchant_code
            if merchant_code is not None
            else _decrypt_merchant(row, settings) if row and row.merchant_ciphertext
            else settings.zibal_merchant.strip()
        )
        candidate = settings.model_copy(update={
            "zibal_enabled": True,
            "zibal_test_mode": test_mode,
            "zibal_merchant": merchant,
            "zibal_callback_url": callback_url,
            "zibal_result_url": result_url,
        })
        ZibalPaymentProvider(candidate).ensure_ready()

    now = datetime.now(timezone.utc)
    if row is None:
        row = ZibalGatewayConfiguration(id=1, created_at=now)
    row.merchant_ciphertext = ciphertext
    row.merchant_last4 = last4
    row.enabled = enabled
    row.test_mode = test_mode
    row.callback_url = callback_url
    row.result_url = result_url
    row.updated_by = actor[:255]
    row.version = current_version + 1
    row.updated_at = now
    session.add(row)
    return row
