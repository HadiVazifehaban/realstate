"""Shared-order Zibal checkout, callback verification and reconciliation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings
from app.models.billing import PaymentAttempt, PaymentOrder
from app.models.enums import PaymentOrderStatus
from app.services import agency_referrals, billing
from app.services.zibal import (
    ZibalDeclined,
    ZibalError,
    ZibalPaymentProvider,
    ZibalUncertain,
    ZibalVerifiedPayment,
)

ACTIVE_ATTEMPT_STATUSES = {"REQUESTING", "PENDING", "UNKNOWN", "RECONCILIATION_REQUIRED"}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def public_attempt(attempt: PaymentAttempt, order: PaymentOrder | None = None) -> dict:
    """Expose only the fields needed by the payer; omit provider payloads."""
    return {
        "id": str(attempt.id),
        "order_id": str(attempt.order_id),
        "order_number": order.order_number if order else None,
        "provider": attempt.provider,
        "status": attempt.status,
        "attempt_number": attempt.attempt_number,
        "amount_toman": attempt.amount_toman,
        "currency": attempt.currency,
        "track_id": attempt.gateway_track_id,
        "payment_url": attempt.payment_url if attempt.status == "PENDING" else None,
        "reference_id": attempt.gateway_reference_id,
        "failure_code": attempt.failure_code,
        "created_at": attempt.created_at.isoformat(),
        "updated_at": attempt.updated_at.isoformat(),
    }


async def start_zibal_checkout(
    session: AsyncSession,
    *,
    order_id: uuid.UUID,
    provider: ZibalPaymentProvider,
    settings: Settings,
    request_id: str = "",
    ip_address: str = "",
    user_agent: str = "",
    now: datetime | None = None,
) -> tuple[PaymentOrder, PaymentAttempt]:
    """Create/reuse one in-flight attempt, then call Zibal outside DB locks."""
    now = _utc(now or datetime.now(timezone.utc))
    provider.ensure_ready()

    order = (await session.exec(
        select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update()
    )).first()
    if order is None:
        raise LookupError("سفارش پیدا نشد.")
    if order.payment_method != "ZIBAL":
        raise ValueError("این سفارش برای پرداخت زیبال ایجاد نشده است.")
    if _utc(order.expires_at) <= now:
        order.status = PaymentOrderStatus.EXPIRED
        order.version += 1
        if order.referral_invoice_applied:
            await agency_referrals.settle_order_credits(session, order_id=order.id, successful=False)
        session.add(order)
        await session.commit()
        raise ValueError("مهلت پرداخت این سفارش پایان یافته است.")
    if order.status in {
        PaymentOrderStatus.APPROVED,
        PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION,
        PaymentOrderStatus.CANCELLED,
        PaymentOrderStatus.EXPIRED,
        PaymentOrderStatus.REJECTED,
    }:
        raise ValueError("این سفارش دیگر قابل پرداخت نیست.")

    latest = (await session.exec(
        select(PaymentAttempt)
        .where(PaymentAttempt.order_id == order.id)
        .order_by(PaymentAttempt.attempt_number.desc())
        .limit(1)
        .with_for_update()
    )).first()
    previous_status = order.status
    if latest is not None and latest.status in ACTIVE_ATTEMPT_STATUSES:
        if order.status != PaymentOrderStatus.PENDING_PAYMENT:
            order.status = PaymentOrderStatus.PENDING_PAYMENT
            session.add(order)
            await session.commit()
        return order, latest
    if latest is not None and latest.status == "PAID":
        return order, latest

    attempt_number = (latest.attempt_number + 1) if latest else 1
    attempt = PaymentAttempt(
        order_id=order.id,
        attempt_number=attempt_number,
        idempotency_key=f"zibal:{order.id}:{attempt_number}",
        provider="ZIBAL",
        status="REQUESTING",
        amount_toman=order.amount_toman,
        amount_rial=order.amount_toman * 10,
        requested_at=now,
        created_at=now,
        updated_at=now,
    )
    order.status = PaymentOrderStatus.PENDING_PAYMENT
    order.version += 1
    session.add(attempt)
    session.add(order)
    session.add(billing.audit_entry(
        actor=order.user_id,
        actor_role="user",
        action="zibal_checkout_requested",
        entity_id=order.id,
        before={"status": previous_status.value},
        after={"status": PaymentOrderStatus.PENDING_PAYMENT.value, "attempt_number": attempt_number},
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    ))
    await session.commit()

    # Do not start a new SQL transaction before the network request. Both ORM
    # rows were populated locally and the Session is configured not to expire on
    # commit; the response is written in a new, short transaction afterwards.
    try:
        result = await provider.create_payment(
            amount_rial=attempt.amount_rial,
            order_number=f"{order.order_number}-{attempt_number}",
            description=f"اشتراک شکارچی {order.plan} - {order.order_number}",
        )
    except ZibalError as exc:
        attempt = (await session.exec(
            select(PaymentAttempt).where(PaymentAttempt.id == attempt.id).with_for_update()
        )).first()
        order = (await session.exec(
            select(PaymentOrder).where(PaymentOrder.id == order.id).with_for_update()
        )).first()
        if attempt is None or order is None:
            await session.rollback()
            raise RuntimeError("سفارش یا تلاش پرداخت پس از پاسخ زیبال پیدا نشد.") from exc
        attempt.status = "UNKNOWN" if exc.uncertain else "FAILED"
        attempt.failure_code = exc.code
        attempt.updated_at = datetime.now(timezone.utc)
        if not exc.uncertain and order.status == PaymentOrderStatus.PENDING_PAYMENT:
            order.status = PaymentOrderStatus.CREATED
            order.version += 1
        session.add(attempt)
        session.add(order)
        session.add(billing.audit_entry(
            actor="zibal",
            actor_role="payment_provider",
            action="zibal_checkout_unknown" if exc.uncertain else "zibal_checkout_failed",
            entity_id=order.id,
            before={"status": PaymentOrderStatus.PENDING_PAYMENT.value},
            after={"attempt_status": attempt.status, "failure_code": exc.code},
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        ))
        await session.commit()
        await session.refresh(attempt)
        await session.refresh(order)
        return order, attempt

    attempt = (await session.exec(
        select(PaymentAttempt).where(PaymentAttempt.id == attempt.id).with_for_update()
    )).first()
    order = (await session.exec(
        select(PaymentOrder).where(PaymentOrder.id == order.id).with_for_update()
    )).first()
    if attempt is None or order is None:
        await session.rollback()
        raise RuntimeError("سفارش یا تلاش پرداخت پس از پاسخ زیبال پیدا نشد.")
    attempt.status = "PENDING"
    attempt.gateway_track_id = result.track_id
    attempt.payment_url = result.payment_url
    attempt.gateway_result_code = result.result_code
    attempt.updated_at = datetime.now(timezone.utc)
    session.add(attempt)
    session.add(billing.audit_entry(
        actor="zibal",
        actor_role="payment_provider",
        action="zibal_payment_created",
        entity_id=order.id,
        after={"attempt_id": str(attempt.id), "track_id": result.track_id, "status": attempt.status},
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    ))
    await session.commit()
    await session.refresh(attempt)
    await session.refresh(order)
    return order, attempt


async def _apply_verified_payment(
    session: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    verification: ZibalVerifiedPayment,
    request_id: str = "",
    ip_address: str = "",
    user_agent: str = "",
    now: datetime | None = None,
) -> tuple[PaymentOrder, PaymentAttempt, str]:
    now = now or datetime.now(timezone.utc)
    attempt = (await session.exec(
        select(PaymentAttempt).where(PaymentAttempt.id == attempt_id).with_for_update()
    )).first()
    if attempt is None:
        raise LookupError("تلاش پرداخت پیدا نشد.")
    order = (await session.exec(
        select(PaymentOrder).where(PaymentOrder.id == attempt.order_id).with_for_update()
    )).first()
    if order is None:
        raise LookupError("سفارش پرداخت پیدا نشد.")
    if attempt.provider != "ZIBAL" or attempt.gateway_track_id != verification.track_id:
        raise ValueError("تراکنش زیبال با سفارش متناظر نیست.")
    if attempt.status == "PAID":
        return order, attempt, "success"
    if verification.status != "PAID":
        previous_attempt_status = attempt.status
        attempt.status = "PENDING"
        attempt.last_inquired_at = now
        attempt.updated_at = now
        session.add(attempt)
        session.add(billing.audit_entry(
            actor="zibal", actor_role="payment_provider", action="zibal_verification_pending",
            entity_id=order.id,
            before={"attempt_status": previous_attempt_status},
            after={"attempt_status": attempt.status, "attempt_id": str(attempt.id)},
            request_id=request_id, ip_address=ip_address, user_agent=user_agent,
        ))
        await session.commit()
        return order, attempt, "pending"

    expected_rial = order.amount_toman * 10
    if verification.amount_rial != expected_rial or attempt.amount_rial != expected_rial:
        attempt.status = "RECONCILIATION_REQUIRED"
        attempt.failure_code = "verified_amount_mismatch"
        attempt.gateway_reference_id = verification.reference_id or None
        attempt.gateway_result_code = verification.result_code
        attempt.updated_at = now
        session.add(attempt)
        session.add(billing.audit_entry(
            actor="zibal", actor_role="payment_provider", action="zibal_amount_mismatch",
            entity_id=order.id,
            before={"amount_rial": expected_rial},
            after={"amount_rial": verification.amount_rial, "attempt_id": str(attempt.id)},
            request_id=request_id, ip_address=ip_address, user_agent=user_agent,
        ))
        await session.commit()
        return order, attempt, "reconciliation_required"

    if order.status in {PaymentOrderStatus.APPROVED, PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION}:
        attempt.status = "RECONCILIATION_REQUIRED"
        attempt.failure_code = "duplicate_payment_requires_reconciliation"
        attempt.gateway_reference_id = verification.reference_id or None
        attempt.verified_at = now
        attempt.updated_at = now
        session.add(attempt)
        await session.commit()
        return order, attempt, "already_settled"
    if order.status not in {PaymentOrderStatus.CREATED, PaymentOrderStatus.PENDING_PAYMENT}:
        attempt.status = "RECONCILIATION_REQUIRED"
        attempt.failure_code = "order_not_payable"
        attempt.gateway_reference_id = verification.reference_id or None
        attempt.updated_at = now
        session.add(attempt)
        session.add(billing.audit_entry(
            actor="zibal", actor_role="payment_provider", action="zibal_order_not_payable",
            entity_id=order.id, after={"order_status": order.status.value, "attempt_id": str(attempt.id)},
            request_id=request_id, ip_address=ip_address, user_agent=user_agent,
        ))
        await session.commit()
        return order, attempt, "reconciliation_required"

    previous_status = order.status
    attempt.status = "PAID"
    attempt.gateway_reference_id = verification.reference_id or None
    attempt.gateway_result_code = verification.result_code
    attempt.verified_at = now
    attempt.updated_at = now

    if order.is_test:
        order.status = PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION
        if order.referral_invoice_applied:
            await agency_referrals.settle_order_credits(session, order_id=order.id, successful=False)
        result = "test_approved_no_activation"
    else:
        order.status = PaymentOrderStatus.APPROVED
        order.approved_at = now
        await billing.activate_subscription(session, order, now)
        # The referral lookup must see the just-approved order in this same
        # transaction to award exactly the first successful paid referral.
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
        result = "success"

    order.version += 1

    session.add(attempt)
    session.add(order)
    session.add(billing.audit_entry(
        actor="zibal", actor_role="payment_provider", action="zibal_payment_verified",
        entity_id=order.id,
        before={"order_status": previous_status.value},
        after={"order_status": order.status.value, "attempt_id": str(attempt.id),
               "amount_toman": order.amount_toman, "reference_id": attempt.gateway_reference_id},
        request_id=request_id, ip_address=ip_address, user_agent=user_agent,
    ))
    await session.commit()
    await session.refresh(order)
    await session.refresh(attempt)
    return order, attempt, result


async def verify_zibal_callback(
    session: AsyncSession,
    *,
    track_id: str,
    provider: ZibalPaymentProvider,
    request_id: str = "",
    ip_address: str = "",
    user_agent: str = "",
    now: datetime | None = None,
) -> tuple[PaymentOrder, PaymentAttempt, str]:
    """Verify a browser callback with Zibal; callback parameters alone never pay."""
    if not track_id or len(track_id) > 64:
        raise LookupError("شناسهٔ تراکنش معتبر نیست.")
    attempt = (await session.exec(
        select(PaymentAttempt).where(
            PaymentAttempt.provider == "ZIBAL",
            PaymentAttempt.gateway_track_id == track_id,
        )
    )).first()
    if attempt is None:
        raise LookupError("تراکنش متناظری برای این شناسه پیدا نشد.")
    attempt_id = attempt.id
    order_id = attempt.order_id
    if attempt.status == "PAID":
        order = await billing.order_by_id(session, order_id)
        if order is None:
            raise LookupError("سفارش پرداخت پیدا نشد.")
        return order, attempt, "success"
    await session.rollback()
    try:
        verification = await provider.verify_payment(track_id=track_id)
    except ZibalUncertain:
        attempt = (await session.exec(
            select(PaymentAttempt).where(PaymentAttempt.id == attempt_id).with_for_update()
        )).first()
        if attempt is not None and attempt.status != "PAID":
            attempt.status = "UNKNOWN"
            attempt.failure_code = "verification_result_unknown"
            attempt.updated_at = _utc(now or datetime.now(timezone.utc))
            session.add(attempt)
            session.add(billing.audit_entry(
                actor="zibal", actor_role="payment_provider", action="zibal_verification_unknown",
                entity_id=order_id,
                after={"attempt_id": str(attempt_id), "attempt_status": attempt.status},
                request_id=request_id, ip_address=ip_address, user_agent=user_agent,
            ))
            await session.commit()
        else:
            await session.rollback()
        order = await billing.order_by_id(session, order_id) if attempt else None
        if order is None or attempt is None:
            raise LookupError("سفارش پرداخت پیدا نشد.")
        return order, attempt, "pending"
    except ZibalDeclined:
        attempt = (await session.exec(
            select(PaymentAttempt).where(PaymentAttempt.id == attempt_id).with_for_update()
        )).first()
        if attempt is None:
            await session.rollback()
            raise LookupError("تلاش پرداخت پیدا نشد.")
        order = (await session.exec(
            select(PaymentOrder).where(PaymentOrder.id == attempt.order_id).with_for_update()
        )).first()
        if order is None:
            await session.rollback()
            raise LookupError("سفارش پرداخت پیدا نشد.")
        if attempt.status != "PAID":
            previous_status = attempt.status
            attempt.status = "FAILED"
            attempt.failure_code = "zibal_verification_declined"
            attempt.updated_at = _utc(now or datetime.now(timezone.utc))
            if order.status == PaymentOrderStatus.PENDING_PAYMENT:
                order.status = PaymentOrderStatus.CREATED
                order.version += 1
            session.add(attempt)
            session.add(order)
            session.add(billing.audit_entry(
                actor="zibal", actor_role="payment_provider", action="zibal_verification_failed",
                entity_id=order.id,
                before={"attempt_status": previous_status},
                after={"attempt_status": attempt.status, "failure_code": attempt.failure_code},
                request_id=request_id, ip_address=ip_address, user_agent=user_agent,
            ))
            await session.commit()
        else:
            await session.rollback()
        return order, attempt, "failed"

    return await _apply_verified_payment(
        session,
        attempt_id=attempt_id,
        verification=verification,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
        now=now,
    )


async def reconcile_zibal_attempt(
    session: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    provider: ZibalPaymentProvider,
    request_id: str = "",
    ip_address: str = "",
    user_agent: str = "",
) -> tuple[PaymentOrder, PaymentAttempt, str]:
    attempt = await session.get(PaymentAttempt, attempt_id)
    if attempt is None or attempt.provider != "ZIBAL":
        raise LookupError("تلاش زیبال پیدا نشد.")
    order_id = attempt.order_id
    if attempt.status == "PAID":
        order = await billing.order_by_id(session, order_id)
        if order is None:
            raise LookupError("سفارش پرداخت پیدا نشد.")
        return order, attempt, "success"
    if not attempt.gateway_track_id:
        order = await billing.order_by_id(session, order_id)
        if order is None:
            raise LookupError("سفارش پرداخت پیدا نشد.")
        return order, attempt, "reconciliation_required"

    track_id = attempt.gateway_track_id
    await session.rollback()
    inquiry = await provider.inquire_payment(track_id=track_id)
    if inquiry.status != "PAID":
        attempt = (await session.exec(
            select(PaymentAttempt).where(PaymentAttempt.id == attempt_id).with_for_update()
        )).first()
        if attempt is None:
            await session.rollback()
            raise LookupError("تلاش پرداخت پیدا نشد.")
        attempt.last_inquired_at = datetime.now(timezone.utc)
        attempt.updated_at = attempt.last_inquired_at
        if attempt.status not in {"FAILED", "PAID", "RECONCILIATION_REQUIRED"}:
            attempt.status = "PENDING"
        session.add(attempt)
        order = await billing.order_by_id(session, order_id)
        if order is not None:
            session.add(billing.audit_entry(
                actor="zibal", actor_role="payment_provider", action="zibal_inquiry_not_paid",
                entity_id=order.id,
                after={"attempt_id": str(attempt.id), "attempt_status": attempt.status},
                request_id=request_id, ip_address=ip_address, user_agent=user_agent,
            ))
        await session.commit()
        await session.refresh(attempt)
        order = await billing.order_by_id(session, order_id)
        if order is None:
            raise LookupError("سفارش پرداخت پیدا نشد.")
        return order, attempt, "pending"

    return await _apply_verified_payment(
        session,
        attempt_id=attempt_id,
        verification=inquiry,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


async def confirm_zibal_attempt_not_paid(
    session: AsyncSession,
    *,
    attempt_id: uuid.UUID,
    actor: str,
    reason: str,
    request_id: str = "",
    ip_address: str = "",
    user_agent: str = "",
    now: datetime | None = None,
) -> tuple[PaymentOrder, PaymentAttempt]:
    """Finance-only terminal resolution after checking Zibal's merchant portal.

    It cancels the order rather than reusing it, so a late success cannot race a
    second payment attempt and activate the same invoice twice.
    """
    reason = reason.strip()
    if len(reason) < 20 or len(reason) > 1000:
        raise ValueError("برای تعیین تکلیف تراکنش، دلیل ۲۰ تا ۱۰۰۰ نویسه‌ای الزامی است.")
    now = now or datetime.now(timezone.utc)
    attempt = (await session.exec(
        select(PaymentAttempt).where(PaymentAttempt.id == attempt_id).with_for_update()
    )).first()
    if attempt is None or attempt.provider != "ZIBAL":
        raise LookupError("تلاش زیبال پیدا نشد.")
    order = (await session.exec(
        select(PaymentOrder).where(PaymentOrder.id == attempt.order_id).with_for_update()
    )).first()
    if order is None:
        raise LookupError("سفارش پرداخت پیدا نشد.")
    if attempt.status not in {"UNKNOWN", "PENDING"} or order.status != PaymentOrderStatus.PENDING_PAYMENT:
        raise ValueError("فقط تراکنش بلاتکلیفِ سفارش در انتظار پرداخت قابل تعیین تکلیف است.")

    previous_attempt = attempt.status
    attempt.status = "FAILED"
    attempt.failure_code = "finance_confirmed_not_paid"
    attempt.updated_at = now
    order.status = PaymentOrderStatus.CANCELLED
    order.version += 1
    if order.referral_invoice_applied:
        await agency_referrals.settle_order_credits(session, order_id=order.id, successful=False)
    session.add(attempt)
    session.add(order)
    session.add(billing.audit_entry(
        actor=actor,
        actor_role="financial_admin",
        action="zibal_confirmed_not_paid",
        entity_id=order.id,
        before={"attempt_status": previous_attempt, "order_status": PaymentOrderStatus.PENDING_PAYMENT.value},
        after={"attempt_status": attempt.status, "order_status": order.status.value, "reason": reason},
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    ))
    await session.commit()
    await session.refresh(attempt)
    await session.refresh(order)
    return order, attempt


async def reconcile_stale_zibal_attempts(
    session: AsyncSession,
    *,
    provider: ZibalPaymentProvider,
    older_than: timedelta = timedelta(minutes=5),
    limit: int = 50,
    now: datetime | None = None,
) -> dict[str, int]:
    """Callable reconciliation job; a scheduler may invoke it outside requests."""
    now = now or datetime.now(timezone.utc)
    rows = (await session.exec(
        select(PaymentAttempt)
        .where(
            PaymentAttempt.provider == "ZIBAL",
            PaymentAttempt.status.in_(["PENDING", "UNKNOWN"]),
            PaymentAttempt.gateway_track_id.is_not(None),
            PaymentAttempt.updated_at <= now - older_than,
        )
        .order_by(PaymentAttempt.updated_at)
        .limit(max(1, min(limit, 200)))
    )).all()
    attempt_ids = [row.id for row in rows]
    await session.rollback()
    counts = {"checked": 0, "paid": 0, "pending": 0, "errors": 0}
    for attempt_id in attempt_ids:
        counts["checked"] += 1
        try:
            _, _, result = await reconcile_zibal_attempt(
                session, attempt_id=attempt_id, provider=provider,
                request_id="zibal-reconciliation-job",
            )
            if result in {"success", "test_approved_no_activation"}:
                counts["paid"] += 1
            else:
                counts["pending"] += 1
        except ZibalError:
            await session.rollback()
            counts["errors"] += 1
    return counts
