"""Phase 5 PII vault access service: quota-gated, always audited.

The rule this module exists to enforce: **no phone number leaves the vault
without (a) an authorised role, (b) remaining tier quota, and (c) an audit
row.** The three are inseparable — :func:`reveal_owner_phone` performs them in
one transaction, so a crash cannot leave an un-audited reveal or an audited
reveal that was never served.

Successful reveals increment the daily counter in ``pii_quota``; denied attempts
are logged too, with ``allowed=False``, so brute-forcing the endpoint is visible
to a supervisor.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.crypto import PiiCipher
from app.models import OwnerAccessLog, PiiQuota, PropertyOwnerPII
from app.models.enums import (
    PII_READER_ROLES,
    TIER_PII_DAILY_QUOTA,
    SaasTier,
    UserRole,
)


class PiiAccessDenied(Exception):
    """Reveal refused: wrong role, quota exhausted, or no such record."""

    def __init__(
        self, reason: str, message: str, *, remaining: int | None = None
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.remaining = remaining


@dataclass(frozen=True)
class PiiRevealResult:
    """What the caller gets back on success."""

    owner_name: str | None
    owner_phone: str | None
    tier: SaasTier
    remaining_quota: int | None  # None = unlimited


def mask_phone(phone: str | None) -> str | None:
    """Render a phone for display without revealing it.

    ``09123456789`` -> ``0912***6789``. Every surface that shows a listing
    without vault access uses this, so the unmasked value only ever comes from
    :func:`reveal_owner_phone`.
    """
    if not phone:
        return phone
    digits = [ch for ch in phone if ch.isdigit()]
    if len(digits) < 4:
        return "*" * len(digits)
    return f"{''.join(digits[:4])}***{''.join(digits[-4:])}"


def quota_for(tier: SaasTier) -> int:
    """Daily allowance; ``-1`` means unlimited."""
    return TIER_PII_DAILY_QUOTA.get(tier, 0)


async def _load_quota_row(
    session: AsyncSession, user_id: uuid.UUID, today: date, tier: SaasTier
) -> PiiQuota | None:
    return (
        await session.exec(
            select(PiiQuota).where(PiiQuota.user_id == user_id, PiiQuota.day == today)
        )
    ).first()


async def remaining_quota(
    session: AsyncSession, user_id: uuid.UUID, tier: SaasTier
) -> int | None:
    """Quota left today; ``None`` for unlimited tiers."""
    daily = quota_for(tier)
    if daily < 0:
        return None
    row = await _load_quota_row(
        session, user_id, datetime.now(timezone.utc).date(), tier
    )
    return max(0, daily - (row.consumed if row else 0))


async def reveal_owner_phone(
    session: AsyncSession,
    *,
    property_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    role: UserRole,
    tier: SaasTier,
    cipher: PiiCipher,
    client_ip: str = "",
    reason: str = "",
) -> PiiRevealResult:
    """Decrypt the owner phone for one property, or raise :class:`PiiAccessDenied`.

    Check order is deliberate: role first (cheapest, and an unauthorised caller
    must not learn whether a record exists), then record, then quota. Every path
    writes an ``OwnerAccessLog`` row before returning or raising.
    """
    today = datetime.now(timezone.utc).date()

    async def _audit(allowed: bool, pii_id: uuid.UUID | None, why: str) -> None:
        session.add(
            OwnerAccessLog(
                pii_id=pii_id,
                property_id=property_id,
                user_id=actor_user_id,
                action="READ",
                allowed=allowed,
                reason=why[:255],
                client_ip=client_ip[:64],
            )
        )
        await session.flush()

    if role not in PII_READER_ROLES:
        await _audit(False, None, "role_not_permitted")
        raise PiiAccessDenied(
            "role_not_permitted",
            "نقش شما اجازهٔ مشاهدهٔ اطلاعات تماس مالک را ندارد.",
        )

    pii = (
        await session.exec(
            select(PropertyOwnerPII).where(PropertyOwnerPII.property_id == property_id)
        )
    ).first()
    if pii is None:
        # Same refusal shape as a permission failure, so the endpoint cannot be
        # used to probe which properties carry a PII record.
        await _audit(False, None, "no_pii_record")
        raise PiiAccessDenied(
            "not_found",
            "برای این فایل اطلاعات تماس ثبت نشده است.",
        )

    daily = quota_for(tier)
    if daily >= 0:
        row = await _load_quota_row(session, actor_user_id, today, tier)
        if row and row.consumed >= daily:
            await _audit(False, pii.id, "quota_exhausted")
            raise PiiAccessDenied(
                "saas_quota_exhausted",
                "سقف روزانهٔ مشاهدهٔ اطلاعات تماس در پلن شما تکمیل شده است.",
                remaining=0,
            )

    # Decrypt only after every gate has passed, then record the spend and the
    # successful audit together.
    owner_name = cipher.decrypt(pii.owner_name_enc)
    owner_phone = cipher.decrypt(pii.owner_phone_enc)
    await _audit(True, pii.id, reason or "quota_consumed")

    remaining: int | None
    if daily < 0:
        remaining = None
    else:
        row = await _load_quota_row(session, actor_user_id, today, tier)
        if row is None:
            row = PiiQuota(user_id=actor_user_id, day=today, tier=tier, consumed=0)
            session.add(row)
        row.consumed += 1
        row.tier = tier
        row.updated_at = datetime.now(timezone.utc)
        await session.flush()
        remaining = max(0, daily - row.consumed)

    return PiiRevealResult(
        owner_name=owner_name,
        owner_phone=owner_phone,
        tier=tier,
        remaining_quota=remaining,
    )
