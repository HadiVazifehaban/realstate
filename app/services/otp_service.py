"""OTP challenge lifecycle for Iran-mobile quick registration.

Flow
----
``request_otp``  validates + rate-limits the mobile, mints a 6-digit code
with ``secrets``, stores **only its HMAC-SHA-256 digest** under a TTL key, and
dispatches it through the SMS adapter. ``verify_otp`` recomputes the hash
with ``hmac.compare_digest``, enforces attempts/expiry/single-use, and on
success mints a short-lived ``registration_token`` (opaque, single-use)
that ``/auth/quick-register`` and ``/auth/professional-registration``
redeem. The raw code never touches logs, responses, or the DB.

Storage is Redis via :class:`OtpStore` (memory fallback only in explicit test
mode). Audit rows are JSON lines on a per-mobile list -- timestamps,
masked mobile, outcome -- never the code.
"""

from __future__ import annotations

import hmac
import json
import secrets
import time
import hashlib
from dataclasses import dataclass

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.mobile import mask_mobile
from app.services.otp_store import OtpStore
from app.services.sms_provider import SmsError, get_sms_provider, last_fake_code

logger = get_logger("app.otp.service")

_store: OtpStore | None = None


def get_store(settings: Settings) -> OtpStore:
    """Process-wide store, namespaced per ``otp_redis_prefix``."""
    global _store
    if _store is None:
        _store = OtpStore(
            settings.redis_url,
            namespace=settings.otp_redis_prefix,
            allow_memory_fallback=settings.otp_test_mode,
        )
    return _store


def reset_store() -> None:
    """Drop the cached store (tests swap settings between cases)."""
    global _store
    _store = None


def hash_code(code: str, mobile_e164: str, secret: str) -> str:
    """HMAC-SHA-256 over mobile and code; raw OTP is never persisted."""
    return hmac.new(secret.encode(), f"{mobile_e164}:{code}".encode(), hashlib.sha256).hexdigest()


def _otp_hmac_secret(settings: Settings) -> str:
    secret = settings.otp_hmac_secret
    if len(secret.encode()) < 32:
        raise SmsError("OTP signing secret is not configured")
    return secret


def mint_code() -> str:
    """Cryptographic 6-digit code (100000..999999, no zero-prefix issues)."""
    return f"{secrets.randbelow(900000) + 100000:06d}"


def mint_token() -> str:
    """Opaque 256-bit token for registration/session hand-offs."""
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class OtpRequestResult:
    ok: bool
    retry_after: int = 0
    message_id: str = ""
    dev_code: str | None = None


@dataclass(frozen=True)
class OtpVerifyResult:
    ok: bool
    registration_token: str = ""
    reason: str = ""


async def _audit(store: OtpStore, settings: Settings, mobile_e164: str, event: str) -> None:
    entry = json.dumps(
        {"ts": int(time.time()), "mobile": mask_mobile(mobile_e164), "event": event}
    )
    await store.rpush_trim(store.key("audit", mobile_e164), entry, settings.otp_audit_keep)


async def request_otp(
    settings: Settings,
    mobile_e164: str,
    *,
    client_ip: str = "",
    purpose: str = "login",
    sms_provider=None,
) -> OtpRequestResult:
    """Mint + dispatch a challenge, enforcing cooldown and hourly budgets."""
    _otp_hmac_secret(settings)
    if not settings.otp_test_mode and settings.sms_provider.strip().lower() == "fake":
        raise SmsError("Real SMS delivery is not configured")
    store = get_store(settings)
    request_lock_key = store.key("request-lock", mobile_e164)
    request_lock_token = mint_token()
    lock_ttl = max(10, settings.otp_request_cooldown_seconds)
    if not await store.set(request_lock_key, request_lock_token, ex=lock_ttl, nx=True):
        await _audit(store, settings, mobile_e164, "request:inflight")
        return OtpRequestResult(ok=False, retry_after=max(1, await store.ttl(request_lock_key)))
    try:
        return await _request_otp_locked(
            settings, mobile_e164, client_ip=client_ip, purpose=purpose,
            sms_provider=sms_provider, store=store,
        )
    finally:
        await store.compare_and_delete(request_lock_key, request_lock_token)


async def _request_otp_locked(
    settings: Settings,
    mobile_e164: str,
    *,
    client_ip: str,
    purpose: str,
    sms_provider,
    store: OtpStore,
) -> OtpRequestResult:
    secret = _otp_hmac_secret(settings)
    now = int(time.time())
    hour = now // 3600

    cooldown_key = store.key("cooldown", mobile_e164)
    if await store.get(cooldown_key):
        ttl = await store.ttl(cooldown_key)
        await _audit(store, settings, mobile_e164, "request:cooldown")
        return OtpRequestResult(ok=False, retry_after=max(1, ttl))

    hour_key = store.key("hour", mobile_e164, str(hour))
    used = await store.incr(hour_key)
    if used == 1:
        await store.expire(hour_key, 3600)
    if used > settings.otp_max_requests_per_hour:
        await _audit(store, settings, mobile_e164, "request:hour_limit")
        return OtpRequestResult(ok=False, retry_after=3600 - (now % 3600))

    if client_ip:
        ip_key = store.key("ip", client_ip, str(hour))
        ip_used = await store.incr(ip_key)
        if ip_used == 1:
            await store.expire(ip_key, 3600)
        if ip_used > settings.otp_max_requests_per_ip_hour:
            await _audit(store, settings, mobile_e164, "request:ip_limit")
            return OtpRequestResult(ok=False, retry_after=3600 - (now % 3600))

    day_key = store.key("day", mobile_e164, str(now // 86400))
    daily_used = await store.incr(day_key)
    if daily_used == 1:
        await store.expire(day_key, 86400 - (now % 86400))
    if daily_used > settings.otp_max_requests_per_day:
        await _audit(store, settings, mobile_e164, "request:day_limit")
        return OtpRequestResult(ok=False, retry_after=86400 - (now % 86400))

    code = mint_code()
    challenge_key = store.key("challenge", mobile_e164)
    payload = json.dumps({"hash": hash_code(code, mobile_e164, secret), "attempts": 0, "purpose": purpose})
    await store.set(challenge_key, payload, ex=settings.otp_ttl_seconds)
    await store.set(cooldown_key, "1", ex=settings.otp_request_cooldown_seconds)

    dev_code: str | None = code if settings.otp_test_mode else None
    try:
        if settings.otp_test_mode:
            message_id = f"fake-{now}"
            from app.services.sms_provider import _FAKE_OUTBOX

            _FAKE_OUTBOX[mobile_e164] = {"code": code, "id": message_id}
        else:
            provider = sms_provider or get_sms_provider(settings)
            message_id = await provider.send_otp(mobile_e164, code)
    except SmsError:
        await store.delete(challenge_key, cooldown_key)
        await _audit(store, settings, mobile_e164, "request:sms_failed")
        raise
    await _audit(store, settings, mobile_e164, "request:sent")
    masked = mask_mobile(mobile_e164)
    logger.info("otp requested for %s purpose=%s", masked, purpose)
    return OtpRequestResult(ok=True, message_id=message_id, dev_code=dev_code)

async def verify_otp(
    settings: Settings,
    mobile_e164: str,
    code: str,
) -> OtpVerifyResult:
    """Check a code; on success consume the challenge and mint a token.

    Every outcome -- including success -- answers the same generic Persian
    message at the API layer, so callers cannot probe account existence.
    """
    store = get_store(settings)
    secret = _otp_hmac_secret(settings)
    challenge_key = store.key("challenge", mobile_e164)
    raw = await store.get(challenge_key)
    if not raw:
        await _audit(store, settings, mobile_e164, "verify:missing_or_expired")
        return OtpVerifyResult(ok=False, reason="expired")
    try:
        challenge = json.loads(raw)
    except ValueError:
        await store.delete(challenge_key)
        return OtpVerifyResult(ok=False, reason="expired")

    expected_hash = str(challenge.get("hash", ""))
    candidate = (code or "").strip()
    match = bool(candidate) and hmac.compare_digest(hash_code(candidate, mobile_e164, secret), expected_hash)

    if not match:
        attempt_result = await store.increment_challenge_attempts(
            challenge_key, raw, settings.otp_max_attempts
        )
        if attempt_result == 1:
            await _audit(store, settings, mobile_e164, "verify:attempts_exhausted")
        elif attempt_result == 0:
            await _audit(store, settings, mobile_e164, "verify:wrong")
        else:
            await _audit(store, settings, mobile_e164, "verify:stale")
        return OtpVerifyResult(ok=False, reason="invalid" if attempt_result >= 0 else "expired")

    # Correct code: single-use consume FIRST, then mint the hand-off token.
    # ``compare_and_delete`` is atomic (Lua on Redis, locked on memory), so a
    # replayed request racing this one finds nothing to redeem.
    consumed = await store.compare_and_delete(challenge_key, raw)
    if not consumed:
        await _audit(store, settings, mobile_e164, "verify:replay")
        return OtpVerifyResult(ok=False, reason="expired")

    token = mint_token()
    token_key = store.key("regtoken", token)
    await store.set(
        token_key,
        json.dumps({"mobile": mobile_e164, "ts": int(time.time())}),
        ex=settings.registration_token_ttl_minutes * 60,
    )
    await store.set(
        store.key("verified", mobile_e164),
        "1",
        ex=settings.mobile_verified_grace_seconds,
    )
    await _audit(store, settings, mobile_e164, "verify:ok")
    logger.info("otp verified for %s", mask_mobile(mobile_e164))
    return OtpVerifyResult(ok=True, registration_token=token)


async def consume_registration_token(
    settings: Settings, token: str
) -> str | None:
    """Redeem a ``registration_token`` once; return the verified mobile."""
    if not token:
        return None
    store = get_store(settings)
    token_key = store.key("regtoken", token)
    raw = await store.get(token_key)
    if not raw:
        return None
    try:
        mobile = str(json.loads(raw).get("mobile", ""))
    except ValueError:
        return None
    if not mobile:
        return None
    if not await store.compare_and_delete(token_key, raw):
        return None
    return mobile


async def is_mobile_verified(settings: Settings, mobile_e164: str) -> bool:
    """True while the post-verify grace marker survives in Redis."""
    return bool(await get_store(settings).get(f"{settings.otp_redis_prefix}:verified:{mobile_e164}"))


async def audit_trail(settings: Settings, mobile_e164: str) -> list[dict]:
    """Recent OTP events for a mobile (masked; for support/debugging)."""
    store = get_store(settings)
    out: list[dict] = []
    for raw in await store.lrange(store.key("audit", mobile_e164)):
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


__all__ = [
    "OtpRequestResult",
    "OtpVerifyResult",
    "audit_trail",
    "consume_registration_token",
    "hash_code",
    "is_mobile_verified",
    "mint_code",
    "mint_token",
    "request_otp",
    "reset_store",
    "verify_otp",
]
