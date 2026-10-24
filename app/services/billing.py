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
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings, get_settings
from app.models.billing import (
    AgencySubscription,
    FinancialAuditLog,
    PaymentOrder,
    PaymentReceipt,
    PaymentReview,
)
from app.models.enums import PaymentEnvironmentMode, PaymentOrderStatus, PaymentReviewDecision


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
    PaymentOrderStatus.CREATED: frozenset({PaymentOrderStatus.AWAITING_TRANSFER, PaymentOrderStatus.CANCELLED}),
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
    }


def _audit(
    *, actor: str, actor_role: str, action: str, entity_id: uuid.UUID,
    before: dict | None = None, after: dict | None = None, request_id: str = "",
    ip_address: str = "", user_agent: str = "",
) -> FinancialAuditLog:
    return FinancialAuditLog(
        actor_user_id=actor,
        actor_role=actor_role,
        action=action,
        entity_type="payment_order",
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
    settings: Settings | None = None,
) -> tuple[PaymentOrder, Plan]:
    settings = settings or get_settings()
    if plan_id not in PLANS or plan_id == "free":
        raise ValueError("پلن انتخاب‌شده برای خرید معتبر نیست.")
    plan = PLANS[plan_id]
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
        payment_method="CARD_TO_CARD",
        environment_mode=PaymentEnvironmentMode.TEST if test else PaymentEnvironmentMode.LIVE,
        is_test=test,
        card_number_snapshot_encrypted=encrypted_card,
        card_last4=card_digits[-4:] if len(card_digits) == 16 else "0000",
        card_holder_snapshot=settings.payment_card_holder[:255],
        card_configured_snapshot=configured,
        status=PaymentOrderStatus.AWAITING_TRANSFER,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    session.add(order)
    await session.flush()
    session.add(_audit(actor=user_id, actor_role="user", action="order_created", entity_id=order.id,
                       after={"status": order.status.value, "plan": plan.id, "amount_toman": plan.price_toman, "is_test": test}))
    await session.commit()
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
    live = not order.is_test and order.card_configured_snapshot
    digits = decrypt_card_snapshot(order, settings) if live else None
    if live and not digits:
        live = False
    return {
        "id": str(order.id), "order_number": order.order_number, "plan": order.plan,
        "amount_toman": order.amount_toman, "payment_method": order.payment_method,
        "environment_mode": order.environment_mode.value, "is_test": order.is_test,
        "status": order.status.value,
        "card_number": digits if live else None,
        "card_last4": order.card_last4 if live else None,
        "card_holder": order.card_holder_snapshot if live else None,
        "card_configured": live,
        "test_warning": "شماره کارت فعلاً آزمایشی است. لطفاً وجهی واریز نکنید." if order.is_test else None,
        "created_at": order.created_at.isoformat(), "expires_at": order.expires_at.isoformat(),
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
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
    plan = PLANS[order.plan]
    query = select(AgencySubscription).where(
        AgencySubscription.agency_id == order.agency_id,
        AgencySubscription.status == "active",
    ).order_by(AgencySubscription.expires_at.desc()).with_for_update()
    current = (await session.exec(query)).first()
    base = max(now, current.expires_at) if current and current.expires_at > now else now
    expires = base + timedelta(days=plan.duration_days)
    subscription = AgencySubscription(
        agency_id=order.agency_id, plan=plan.id, status="active", starts_at=base,
        expires_at=expires, listing_quota=plan.listing_quota, sms_quota=plan.sms_quota,
        regions_quota=plan.regions_quota, advisor_quota=plan.advisor_quota,
        is_unlimited=plan.is_unlimited, created_by_order_id=order.id,
    )
    if current:
        current.status = "superseded"
    session.add(subscription)
    order.activated_at = now
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
    elif decision in {PaymentReviewDecision.APPROVED, PaymentReviewDecision.TEST_APPROVED}:
        if order.is_test or not order.card_configured_snapshot:
            if decision is not PaymentReviewDecision.TEST_APPROVED:
                raise ValueError("سفارش آزمایشی هرگز نمی‌تواند اشتراک واقعی را فعال کند.")
            order.status = PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION
        else:
            if decision is not PaymentReviewDecision.APPROVED:
                raise ValueError("برای سفارش واقعی تصمیم تأیید واقعی ثبت کنید.")
            order.status = PaymentOrderStatus.APPROVED
            order.approved_at = now
            await activate_subscription(session, order, now)
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