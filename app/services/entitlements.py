"""Database-backed subscription entitlement checks for first-party inventory."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.agency_network import Agency
from app.models.agency_user import AgencyUser
from app.models.billing import AgencySubscription
from app.models.property import Property
from app.services.billing import get_plan


@dataclass(frozen=True)
class ListingQuota:
    plan: str
    used: int
    limit: int | None
    unlimited: bool
    remaining: int | None
    period_starts_at: datetime
    expires_at: datetime | None


class EntitlementLimitExceeded(ValueError):
    code = "listing_quota_exceeded"


async def lock_listing_entitlement_scope(
    session: AsyncSession, *, agency_key: str | None, agency_uuid: uuid.UUID | None,
    actor_user_id: uuid.UUID,
) -> None:
    """Serialize listing creates in the same billable scope until its commit."""
    if agency_uuid is not None:
        # A parent row lock coordinates requests from different members of one
        # office. Membership was resolved by the authenticated API dependency.
        agency = (await session.exec(
            select(Agency.id).where(Agency.id == agency_uuid).with_for_update()
        )).first()
        if agency is None:
            raise EntitlementLimitExceeded("دفتر فعال برای سهمیهٔ اشتراک پیدا نشد.")
        return

    if agency_key:
        # Legacy local offices have opaque keys (usually "local") rather than a
        # first-class Agency row. Lock all known members in a stable order.
        member_ids = (await session.exec(
            select(AgencyUser.id).where(AgencyUser.agency_id == agency_key)
            .order_by(AgencyUser.id).with_for_update()
        )).all()
        if member_ids:
            return

    # A personal (non-office) owner has no Agency parent row, so serialize their
    # own writes on the local identity projection row instead.
    actor = (await session.exec(
        select(AgencyUser.id).where(AgencyUser.id == actor_user_id).with_for_update()
    )).first()
    if actor is None:
        raise EntitlementLimitExceeded("هویت محلی کاربر برای بررسی سهمیه پیدا نشد.")


async def get_listing_quota(
    session: AsyncSession,
    *,
    agency_key: str | None,
    agency_uuid: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    now: datetime | None = None,
) -> ListingQuota:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    subscription = None
    if agency_key is not None:
        subscription = (await session.exec(
            select(AgencySubscription)
            .where(
                AgencySubscription.agency_id == agency_key,
                AgencySubscription.status == "active",
                AgencySubscription.starts_at <= now,
                AgencySubscription.expires_at > now,
            )
            .order_by(AgencySubscription.starts_at.desc(), AgencySubscription.created_at.desc())
            .limit(1)
        )).first()

    if subscription is None:
        free = await get_plan(session, "free", include_inactive=True)
        if free is None:
            raise EntitlementLimitExceeded("کاتالوگ پلن پایه در دیتابیس موجود نیست.")
        limit = free.listing_quota
        unlimited = free.is_unlimited
        plan_id = free.id
        period_starts_at = now - timedelta(days=free.duration_days)
        expires_at = None
    else:
        plan_id = subscription.plan
        limit = None if subscription.is_unlimited else subscription.listing_quota
        # A NULL quota is unlimited only when the explicit unlimited flag is on.
        unlimited = bool(subscription.is_unlimited)
        if limit is None and not unlimited:
            limit = 0
        period_starts_at = subscription.starts_at
        expires_at = subscription.expires_at

    if agency_uuid is not None:
        usage_query = (
            select(func.count(Property.id))
            .where(
                Property.agency_id == agency_uuid,
                Property.created_at >= period_starts_at,
                Property.submitter_type.is_not(None),
            )
        )
    elif agency_key is not None:
        usage_query = (
            select(func.count(Property.id))
            .join(AgencyUser, Property.created_by_id == AgencyUser.id)
            .where(
                AgencyUser.agency_id == agency_key,
                Property.agency_id.is_(None),
                Property.created_at >= period_starts_at,
                Property.submitter_type.is_not(None),
            )
        )
    elif actor_user_id is not None:
        usage_query = (
            select(func.count(Property.id))
            .where(
                Property.created_by_id == actor_user_id,
                Property.agency_id.is_(None),
                Property.created_at >= period_starts_at,
                Property.submitter_type.is_not(None),
            )
        )
    else:
        usage_query = select(func.count(Property.id)).where(Property.id.is_(None))
    used = int((await session.exec(usage_query)).one() or 0)
    remaining = None if unlimited else max(0, int(limit or 0) - used)
    return ListingQuota(
        plan=plan_id,
        used=used,
        limit=None if unlimited else int(limit or 0),
        unlimited=unlimited,
        remaining=remaining,
        period_starts_at=period_starts_at,
        expires_at=expires_at,
    )


async def resolve_local_actor_id(session: AsyncSession, *, username: str) -> uuid.UUID | None:
    row = (await session.exec(
        select(AgencyUser.id).where(AgencyUser.username == username[:64])
    )).first()
    return row


async def enforce_listing_quota(
    session: AsyncSession,
    *,
    agency_key: str | None,
    agency_uuid: uuid.UUID | None,
    actor_user_id: uuid.UUID,
    now: datetime | None = None,
) -> ListingQuota:
    quota = await get_listing_quota(
        session, agency_key=agency_key, agency_uuid=agency_uuid,
        actor_user_id=actor_user_id, now=now
    )
    if not quota.unlimited and quota.used >= int(quota.limit or 0):
        raise EntitlementLimitExceeded(
            f"سهمیهٔ ثبت آگهی پلن {quota.plan} تکمیل شده است ({quota.used}/{quota.limit})."
        )
    return quota
