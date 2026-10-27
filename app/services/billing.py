"""Business rules and secure private receipt storage for manual billing."""

from __future__ import annotations

import hashlib
import io
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image
from cryptography.fernet import Fernet
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings, get_settings
from app.models.billing import (
    AgencySubscription,
    FinancialAuditLog,
    PaymentAttempt,
    PaymentOrder,
    PaymentReceipt,
    PaymentReview,
    SubscriptionPlan,
)
from app.models.enums import PaymentEnvironmentMode, PaymentOrderStatus, PaymentReviewDecision
from app.services import agency_referrals
from app.services.zibal import ZibalPaymentProvider


@dataclass(frozen=True)
class Plan:
    id: str
    title: str
    price_toman: int
    duration_days: int
    listing_quota: int | None
    sms_quota: int
    regions_quota: int
    advisor_quota: int | None
    is_unlimited: bool = False
    features: tuple[str, ...] = ()
    description: str = ""
    is_active: bool = True
    sort_order: int = 0


PLANS: dict[str, Plan] = {
    "free": Plan("free", "پایه رایگان", 0, 30, 3, 0, 0, 1, features=("AVM پایه",)),
    "monthly": Plan("monthly", "برنز ماهانه", 499_000, 30, 50, 30, 1, 3),
    "quarterly": Plan("quarterly", "نقره‌ای فصلی", 1_347_000, 90, 150, 100, 2, 8),
    "yearly": Plan(
        "yearly", "طلایی سالانه", 4_790_000, 365, None, 500, 1000, None, True,
        ("PDF تحلیلی AVM", "تیک آبی اعتبارسنجی", "مدیر حساب اختصاصی"),
    ),
}

ALLOWED_TRANSITIONS: dict[PaymentOrderStatus, frozenset[PaymentOrderStatus]] = {
    PaymentOrderStatus.CREATED: frozenset({PaymentOrderStatus.AWAITING_TRANSFER, PaymentOrderStatus.PENDING_PAYMENT, PaymentOrderStatus.CANCELLED}),
    PaymentOrderStatus.PENDING_PAYMENT: frozenset({PaymentOrderStatus.CREATED, PaymentOrderStatus.APPROVED, PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION, PaymentOrderStatus.CANCELLED}),
    PaymentOrderStatus.AWAITING_TRANSFER: frozenset({PaymentOrderStatus.RECEIPT_SUBMITTED, PaymentOrderStatus.EXPIRED, PaymentOrderStatus.CANCELLED}),
    PaymentOrderStatus.RECEIPT_SUBMITTED: frozenset({PaymentOrderStatus.UNDER_REVIEW, PaymentOrderStatus.REJECTED}),
    PaymentOrderStatus.UNDER_REVIEW: frozenset({PaymentOrderStatus.APPROVED, PaymentOrderStatus.REJECTED, PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION}),
    PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION: frozenset(),
    PaymentOrderStatus.APPROVED: frozenset(),
    PaymentOrderStatus.REJECTED: frozenset(),
    PaymentOrderStatus.EXPIRED: frozenset(),
    PaymentOrderStatus.CANCELLED: frozenset(),
}


def _cipher(settings: Settings) -> Fernet:
    key = settings.payment_encryption_key.strip()
    if not key:
        raise RuntimeError("PAYMENT_ENCRYPTION_KEY must be configured before creating payment orders")
    return Fernet(key.encode("ascii"))


def payment_is_live(settings: Settings) -> bool:
    digits = re.sub(r"\D", "", settings.payment_card_number)
    return bool(
        settings.payment_method == "CARD_TO_CARD"
        and settings.payment_card_configured
        and settings.payment_card_owner_verified
        and len(digits) == 16
        and digits != "0000000000000000"
    )


def public_plan(plan: Plan) -> dict:
    return {
        "id": plan.id,
        "title": plan.title,
        "price_toman": plan.price_toman,
        "duration_days": plan.duration_days,
        "listing_quota": plan.listing_quota,
        "sms_quota": plan.sms_quota,
        "regions_quota": plan.regions_quota,
        "advisor_quota": plan.advisor_quota,
        "is_unlimited": plan.is_unlimited,
        "features": list(plan.features),
        "description": plan.description,
        "is_active": plan.is_active,
        "sort_order": plan.sort_order,
    }


def plan_from_snapshot(snapshot: dict | None, *, fallback: Plan | None = None) -> Plan:
    if not snapshot:
        if fallback is None:
            raise ValueError("Snapshot پلن موجود نیست.")
        return fallback
    return Plan(
        id=str(snapshot["id"]), title=str(snapshot["title"]),
        price_toman=int(snapshot["price_toman"]), duration_days=int(snapshot["duration_days"]),
        listing_quota=snapshot.get("listing_quota"), sms_quota=int(snapshot.get("sms_quota", 0)),
        regions_quota=int(snapshot.get("regions_quota", 0)), advisor_quota=snapshot.get("advisor_quota"),
        is_unlimited=bool(snapshot.get("is_unlimited", False)),
        features=tuple(snapshot.get("features") or ()), description=str(snapshot.get("description", "")),
        is_active=bool(snapshot.get("is_active", True)), sort_order=int(snapshot.get("sort_order", 0)),
    )


def _plan_record_to_plan(row: SubscriptionPlan) -> Plan:
    return Plan(
        id=row.id, title=row.title, price_toman=row.price_toman, duration_days=row.duration_days,
        listing_quota=row.listing_quota, sms_quota=row.sms_quota, regions_quota=row.regions_quota,
        advisor_quota=row.advisor_quota, is_unlimited=row.is_unlimited,
        features=tuple(row.features or ()), description=row.description, is_active=row.is_active,
        sort_order=row.sort_order,
    )


async def get_plan(session: AsyncSession, plan_id: str, *, include_inactive: bool = False) -> Plan | None:
    row = await session.get(SubscriptionPlan, plan_id)
    if row is None or (not include_inactive and not row.is_active):
        return None
    return _plan_record_to_plan(row)


async def list_plans(session: AsyncSession, *, include_inactive: bool = False) -> list[Plan]:
    query = select(SubscriptionPlan)
    if not include_inactive:
        query = query.where(SubscriptionPlan.is_active.is_(True))
    rows = (await session.exec(query.order_by(SubscriptionPlan.sort_order, SubscriptionPlan.id))).all()
    return [_plan_record_to_plan(row) for row in rows]


def _audit(
    *, actor: str, actor_role: str, action: str, entity_id: uuid.UUID,
    before: dict | None = None, after: dict | None = None, request_id: str = "",
    ip_address: str = "", user_agent: str = "", entity_type: str = "payment_order",
) -> FinancialAuditLog:
    return FinancialAuditLog(
        actor_user_id=actor,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type[:64],
        entity_id=entity_id,
        before_data=before or {},
        after_data=after or {},
        request_id=request_id[:128],
        ip_address=ip_address[:64],
        user_agent=user_agent[:512],
    )


#: Public alias so API modules can write audit rows without reaching into the
#: private helper.
audit_entry = _audit


async def create_order(
    session: AsyncSession, *, agency_id: str, user_id: str, plan_id: str,
    settings: Settings | None = None, payment_method: str = "CARD_TO_CARD",
    idempotency_key: str | None = None,
) -> tuple[PaymentOrder, Plan]:
    settings = settings or get_settings()
    plan_id = plan_id.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", plan_id):
        raise ValueError("شناسهٔ پلن معتبر نیست.")
    payment_method = payment_method.strip().upper()
    if payment_method not in {"CARD_TO_CARD", "ZIBAL"}:
        raise ValueError("روش پرداخت انتخاب‌شده معتبر نیست.")
    idempotency_key = (idempotency_key or "").strip() or None
    if idempotency_key and (len(idempotency_key) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key)):
        raise ValueError("کلید تکرارپذیری سفارش معتبر نیست.")

    if idempotency_key:
        previous_order = (await session.exec(select(PaymentOrder).where(
            PaymentOrder.agency_id == agency_id,
            PaymentOrder.idempotency_key == idempotency_key,
        ))).first()
        if previous_order is not None:
            if previous_order.plan != plan_id or previous_order.payment_method != payment_method:
                raise ValueError("کلید تکرارپذیری قبلاً برای سفارش متفاوتی استفاده شده است.")
            fallback = PLANS.get(previous_order.plan)
            if previous_order.plan_snapshot:
                return previous_order, plan_from_snapshot(previous_order.plan_snapshot, fallback=fallback)
            previous_plan = await get_plan(session, previous_order.plan, include_inactive=True)
            if previous_plan is None:
                previous_plan = fallback
            if previous_plan is None:
                raise ValueError("پلن فاکتور قبلی دیگر در کاتالوگ پیدا نمی‌شود.")
            return previous_order, previous_plan

    plan = await get_plan(session, plan_id)
    if plan is None or plan.id == "free" or plan.price_toman <= 0:
        raise ValueError("پلن انتخاب‌شده برای خرید معتبر یا فعال نیست.")
    if payment_method == "ZIBAL":
        # The gateway is doubly opt-in and has no card data to encrypt.
        ZibalPaymentProvider(settings).ensure_ready()
        card_digits = ""
        configured = False
        test = settings.zibal_test_mode
        encrypted_card = None
    else:
        card_digits = re.sub(r"\D", "", settings.payment_card_number)
        configured = payment_is_live(settings)
        # An invalid/unverified configured destination fails closed into test mode;
        # no placeholder is represented as an actual bank card in public responses.
        test = not configured
        encrypted_card = _cipher(settings).encrypt(card_digits.encode()).decode() if len(card_digits) == 16 else _cipher(settings).encrypt(b"0000000000000000").decode()
    order = PaymentOrder(
        order_number=f"SHK-{datetime.now(timezone.utc):%y%m%d}-{uuid.uuid4().hex[:10].upper()}",
        agency_id=agency_id,
        user_id=user_id,
        plan=plan.id,
        amount_toman=plan.price_toman,
        base_amount_toman=plan.price_toman,
        payment_method=payment_method,
        idempotency_key=idempotency_key,
        plan_snapshot=public_plan(plan),
        environment_mode=PaymentEnvironmentMode.TEST if test else PaymentEnvironmentMode.LIVE,
        is_test=test,
        card_number_snapshot_encrypted=encrypted_card,
        card_last4=card_digits[-4:] if len(card_digits) == 16 else None,
        card_holder_snapshot=settings.payment_card_holder[:255] if payment_method == "CARD_TO_CARD" else None,
        card_configured_snapshot=configured,
        status=PaymentOrderStatus.AWAITING_TRANSFER if payment_method == "CARD_TO_CARD" else PaymentOrderStatus.CREATED,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    session.add(order)
    await session.flush()
    discount_percent, credit_count = 0, 0
    # Credits are renewed discounts for an existing agency only. Do not discount
    # the invitee's first purchase, which is the qualification event itself.
    prior_paid = (await session.exec(
        select(PaymentOrder.id).where(
            PaymentOrder.agency_id == agency_id,
            PaymentOrder.id != order.id,
            PaymentOrder.plan != "free",
            PaymentOrder.is_test.is_(False),
            PaymentOrder.status == PaymentOrderStatus.APPROVED,
        ).limit(1)
    )).first()
    # Referral credits are only applicable to renewals of an already-paid
    # subscription. This excludes the invitee's qualifying first purchase.
    current_subscription = (await session.exec(
        select(AgencySubscription.id).where(
            AgencySubscription.agency_id == agency_id,
            AgencySubscription.status == "active",
            AgencySubscription.expires_at > datetime.now(timezone.utc),
        ).limit(1)
    )).first()
    try:
        agency_uuid = uuid.UUID(agency_id)
    except (ValueError, TypeError):
        agency_uuid = None
    renewal_active = current_subscription is not None
    if agency_uuid is not None:
        from app.models.agency_network import Agency

        linked_agency = await session.get(Agency, agency_uuid)
        renewal_active = linked_agency is not None and linked_agency.status.value != "SUSPENDED"
    if prior_paid is None or not renewal_active:
        discount_percent, credit_count = 0, 0
    else:
        discount_percent, credit_count = await agency_referrals.reserve_credits_for_order(
            session, agency_id=agency_id, order_id=order.id
        )
    discount_amount = (plan.price_toman * discount_percent) // 100
    order.amount_toman = plan.price_toman - discount_amount
    order.base_amount_toman = plan.price_toman
    order.discount_percent = discount_percent
    order.discount_amount_toman = discount_amount
    order.referral_credit_count = credit_count
    order.referral_invoice_applied = credit_count > 0
    session.add(_audit(actor=user_id, actor_role="user", action="order_created", entity_id=order.id,
                       after={"status": order.status.value, "plan": plan.id, "base_amount_toman": plan.price_toman,
                              "referral_discount_percent": discount_percent, "referral_discount_toman": discount_amount,
                              "referral_credit_count": credit_count, "amount_toman": order.amount_toman, "is_test": test}))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        if idempotency_key:
            previous_order = (await session.exec(select(PaymentOrder).where(
                PaymentOrder.agency_id == agency_id,
                PaymentOrder.idempotency_key == idempotency_key,
            ))).first()
            if previous_order is not None:
                if previous_order.plan != plan_id or previous_order.payment_method != payment_method:
                    raise ValueError("کلید تکرارپذیری قبلاً برای سفارش متفاوتی استفاده شده است.")
                fallback = PLANS.get(previous_order.plan)
                previous_plan = plan_from_snapshot(previous_order.plan_snapshot, fallback=fallback) if previous_order.plan_snapshot else None
                previous_plan = previous_plan or await get_plan(session, previous_order.plan, include_inactive=True) or fallback
                if previous_plan is None:
                    raise ValueError("پلن فاکتور قبلی دیگر در کاتالوگ پیدا نمی‌شود.")
                return previous_order, previous_plan
        raise
    await session.refresh(order)
    return order, plan


def decrypt_card_snapshot(order: PaymentOrder, settings: Settings) -> str | None:
    """Decrypt the stored card snapshot, or ``None`` when it cannot be read.

    The snapshot is only ever rendered for a live, configured order. A missing
    or rotated key must degrade to "no card shown" rather than 500 the whole
    checkout page.
    """
    try:
        cipher = _cipher(settings)
    except RuntimeError:
        return None
    try:
        return cipher.decrypt(order.card_number_snapshot_encrypted.encode()).decode()
    except Exception:  # noqa: BLE001 - a corrupt snapshot must not leak
        return None


def payment_order_public(order: PaymentOrder, *, settings: Settings) -> dict:
    live = order.payment_method == "CARD_TO_CARD" and not order.is_test and order.card_configured_snapshot
    digits = decrypt_card_snapshot(order, settings) if live else None
    if live and not digits:
        live = False
    return {
        "id": str(order.id), "order_number": order.order_number, "plan": order.plan,
        "plan_snapshot": order.plan_snapshot,
        "amount_toman": order.amount_toman, "base_amount_toman": order.base_amount_toman,
        "currency": "IRT",
        "discount_percent": order.discount_percent,
        "discount_amount_toman": order.discount_amount_toman,
        "referral_credit_count": order.referral_credit_count,
        "payment_method": order.payment_method,
        "environment_mode": order.environment_mode.value, "is_test": order.is_test,
        "status": order.status.value,
        "card_number": digits if live else None,
        "card_last4": order.card_last4 if live else None,
        "card_holder": order.card_holder_snapshot if live else None,
        "card_configured": live,
        "test_warning": (
            "این سفارش آزمایشی است؛ وجهی واریز نکنید و اشتراک فعال نمی‌شود."
            if order.is_test and order.payment_method == "ZIBAL"
            else "شماره کارت فعلاً آزمایشی است. لطفاً وجهی واریز نکنید."
            if order.is_test
            else None
        ),
        "created_at": order.created_at.isoformat(), "expires_at": order.expires_at.isoformat(),
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "approved_at": order.approved_at.isoformat() if order.approved_at else None,
    }


def inspect_receipt(data: bytes) -> tuple[str, str]:
    if not data:
        raise ValueError("فایل رسید خالی است.")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
        except Exception as exc:
            raise ValueError("فایل PNG معتبر نیست.") from exc
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
        except Exception as exc:
            raise ValueError("فایل JPEG معتبر نیست.") from exc
        return "image/jpeg", ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
        except Exception as exc:
            raise ValueError("فایل WebP معتبر نیست.") from exc
        return "image/webp", ".webp"
    if data.startswith(b"%PDF-") and b"%%EOF" in data[-2048:]:
        return "application/pdf", ".pdf"
    raise ValueError("فقط فایل JPEG، PNG، WebP یا PDF معتبر پذیرفته می‌شود.")


async def store_receipt(data: bytes, *, settings: Settings) -> tuple[str, str, str]:
    content_type, extension = inspect_receipt(data)
    digest = hashlib.sha256(data).hexdigest()
    storage_key = f"{uuid.uuid4().hex}{extension}"
    root = settings.resolve_path(settings.data_dir) / "private" / "payment-receipts"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / storage_key
    target.write_bytes(data)
    target.chmod(0o600)
    return storage_key, content_type, digest


def receipt_path(storage_key: str, settings: Settings) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}\.(?:jpg|png|webp|pdf)", storage_key):
        raise ValueError("Invalid receipt storage key")
    root = (settings.resolve_path(settings.data_dir) / "private" / "payment-receipts").resolve()
    path = (root / storage_key).resolve()
    if path.parent != root:
        raise ValueError("Invalid receipt storage key")
    return path


async def activate_subscription(session: AsyncSession, order: PaymentOrder, now: datetime) -> AgencySubscription:
    if order.plan_snapshot:
        snapshot = order.plan_snapshot
    else:
        plan = await get_plan(session, order.plan, include_inactive=True) or PLANS.get(order.plan)
        if plan is None:
            raise ValueError("پلن سفارش تاریخی قابل بازیابی نیست.")
        snapshot = public_plan(plan)
    duration_days = int(snapshot["duration_days"])
    query = select(AgencySubscription).where(
        AgencySubscription.agency_id == order.agency_id,
        AgencySubscription.status == "active",
    ).order_by(AgencySubscription.expires_at.desc()).with_for_update()
    current = (await session.exec(query)).first()
    base = max(now, current.expires_at) if current and current.expires_at > now else now
    expires = base + timedelta(days=duration_days)
    subscription = AgencySubscription(
        agency_id=order.agency_id, plan=order.plan, status="active", starts_at=base,
        expires_at=expires,
        listing_quota=snapshot.get("listing_quota"),
        sms_quota=int(snapshot.get("sms_quota", 0)),
        regions_quota=int(snapshot.get("regions_quota", 0)),
        advisor_quota=snapshot.get("advisor_quota"),
        is_unlimited=bool(snapshot.get("is_unlimited", False)),
        created_by_order_id=order.id,
    )
    if current:
        current.status = "superseded"
    session.add(subscription)
    order.activated_at = now
    if order.referral_invoice_applied:
        await agency_referrals.settle_order_credits(session, order_id=order.id, successful=True)
    return subscription


async def order_by_id(session: AsyncSession, order_id: uuid.UUID, *, lock: bool = False) -> PaymentOrder | None:
    query = select(PaymentOrder).where(PaymentOrder.id == order_id)
    if lock:
        query = query.with_for_update()
    return (await session.exec(query)).first()


async def review_order(
    session: AsyncSession, *, order: PaymentOrder, reviewer_id: str,
    decision: PaymentReviewDecision, reason: str, request_id: str = "",
    ip_address: str = "", user_agent: str = "", now: datetime | None = None,
) -> PaymentOrder:
    now = now or datetime.now(timezone.utc)
    if order.status not in {PaymentOrderStatus.RECEIPT_SUBMITTED, PaymentOrderStatus.UNDER_REVIEW}:
        raise ValueError("این سفارش در وضعیت قابل بررسی نیست.")
    if order.expires_at <= now:
        order.status = PaymentOrderStatus.EXPIRED
        if order.referral_invoice_applied:
            await agency_referrals.settle_order_credits(session, order_id=order.id, successful=False)
        session.add(order)
        await session.commit()
        return order
    if decision is PaymentReviewDecision.APPROVED and (order.is_test or not order.card_configured_snapshot):
        raise ValueError("سفارش آزمایشی هرگز نمی‌تواند اشتراک واقعی را فعال کند.")
    if decision is PaymentReviewDecision.TEST_APPROVED and not order.is_test:
        raise ValueError("برای سفارش واقعی تصمیم تأیید واقعی ثبت کنید.")
    receipt = (await session.exec(select(PaymentReceipt).where(PaymentReceipt.order_id == order.id))).first()
    if receipt is None:
        raise ValueError("برای تأیید مالی باید رسید معتبر ثبت شده باشد.")
    previous = order.status
    before = {"status": previous.value, "is_test": order.is_test}
    if decision is PaymentReviewDecision.REJECTED:
        if not reason.strip():
            raise ValueError("دلیل رد درخواست الزامی است.")
        order.status = PaymentOrderStatus.REJECTED
        order.rejected_at = now
        if order.referral_invoice_applied:
            await agency_referrals.settle_order_credits(session, order_id=order.id, successful=False)
        session.add(order)
    elif decision in {PaymentReviewDecision.APPROVED, PaymentReviewDecision.TEST_APPROVED}:
        if order.is_test or not order.card_configured_snapshot:
            if decision is not PaymentReviewDecision.TEST_APPROVED:
                raise ValueError("سفارش آزمایشی هرگز نمی‌تواند اشتراک واقعی را فعال کند.")
            order.status = PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION
            if order.referral_invoice_applied:
                await agency_referrals.settle_order_credits(session, order_id=order.id, successful=False)
            session.add(order)
        else:
            if decision is not PaymentReviewDecision.APPROVED:
                raise ValueError("برای سفارش واقعی تصمیم تأیید واقعی ثبت کنید.")
            order.status = PaymentOrderStatus.APPROVED
            order.approved_at = now
            await activate_subscription(session, order, now)
            # Referral qualification queries the just-approved order; flush it
            # inside the same transaction before checking the first paid order.
            await session.flush()
            try:
                await agency_referrals.complete_first_paid_referral(
                    session, referred_agency_id=order.agency_id, order_id=order.id, now=now
                )
            except ValueError:
                pass
            try:
                await agency_referrals.activate_pending_credits(session, uuid.UUID(order.agency_id))
            except ValueError:
                pass
    else:
        raise ValueError("تصمیم بررسی نامعتبر است.")

    session.add(PaymentReview(
        order_id=order.id, reviewer_user_id=reviewer_id, decision=decision,
        reason=reason.strip()[:2000], previous_status=previous, new_status=order.status,
        is_test_review=order.is_test,
    ))
    session.add(_audit(
        actor=reviewer_id, actor_role="financial_admin", action=f"payment_{decision.value}",
        entity_id=order.id, before=before,
        after={"status": order.status.value, "is_test": order.is_test},
        request_id=request_id, ip_address=ip_address, user_agent=user_agent,
    ))
    order.version += 1
    await session.commit()
    await session.refresh(order)
    return order
