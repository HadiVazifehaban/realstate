from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import Settings
from app.models.billing import PaymentOrder, SubscriptionPlan
from app.models.enums import PaymentEnvironmentMode, PaymentOrderStatus
from app.services import billing
from app.services.zibal import ZibalStartedPayment, ZibalVerifiedPayment
from app.services.zibal_billing import confirm_zibal_attempt_not_paid, start_zibal_checkout, verify_zibal_callback
from tests.conftest import create_sqlite_schema


@pytest.mark.asyncio
async def test_order_idempotency_reuses_same_invoice_and_rejects_payload_changes() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_sqlite_schema(engine, "subscription_plan", "payment_order", "financial_audit_log", "referral_credit", "agency_subscription")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    settings = Settings(payment_encryption_key=Fernet.generate_key().decode())

    async with session_factory() as session:
        session.add_all([SubscriptionPlan(
            id=plan.id, title=plan.title, description=plan.description,
            price_toman=1_500_000 if plan.id == "quarterly" else plan.price_toman,
            duration_days=plan.duration_days, listing_quota=plan.listing_quota,
            sms_quota=plan.sms_quota, regions_quota=plan.regions_quota,
            advisor_quota=plan.advisor_quota, is_unlimited=plan.is_unlimited,
            features=list(plan.features), is_active=plan.is_active, sort_order=plan.sort_order,
        ) for plan in billing.PLANS.values()])
        await session.commit()
        first, _ = await billing.create_order(
            session, agency_id="legacy-agency", user_id="subject-1", plan_id="quarterly",
            payment_method="CARD_TO_CARD", idempotency_key="billing-click-12345678", settings=settings,
        )
        assert first.amount_toman == 1_500_000
        assert first.plan_snapshot["price_toman"] == 1_500_000
        repeated, _ = await billing.create_order(
            session, agency_id="legacy-agency", user_id="subject-1", plan_id="quarterly",
            payment_method="CARD_TO_CARD", idempotency_key="billing-click-12345678", settings=settings,
        )
        assert repeated.id == first.id
        with pytest.raises(ValueError, match="کلید تکرارپذیری"):
            await billing.create_order(
                session, agency_id="legacy-agency", user_id="subject-1", plan_id="monthly",
                payment_method="CARD_TO_CARD", idempotency_key="billing-click-12345678", settings=settings,
            )

    await engine.dispose()


class StubZibal:
    def __init__(self) -> None:
        self.create_calls = 0
        self.verify_calls = 0
        self.verified_amount_rial = 13_470_000

    def ensure_ready(self) -> None:
        return None

    async def create_payment(self, *, amount_rial: int, order_number: str, description: str):
        self.create_calls += 1
        assert amount_rial == 13_470_000
        return ZibalStartedPayment(track_id="zibal-track-1", payment_url="https://gateway.zibal.ir/start/zibal-track-1", result_code=100)

    async def verify_payment(self, *, track_id: str):
        self.verify_calls += 1
        return ZibalVerifiedPayment(
            track_id=track_id, status="PAID", amount_rial=self.verified_amount_rial,
            reference_id="ref-1", result_code=100, source="verify",
        )


@pytest.mark.asyncio
async def test_checkout_is_reused_and_verified_test_payment_never_activates_subscription() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_sqlite_schema(engine, "payment_order", "payment_attempt", "financial_audit_log")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    settings = Settings()
    now = datetime.now(timezone.utc)
    order = PaymentOrder(
        order_number="SHK-260101-TEST",
        agency_id="legacy-agency",
        user_id="keycloak-subject",
        plan="quarterly",
        amount_toman=1_347_000,
        base_amount_toman=1_347_000,
        payment_method="ZIBAL",
        environment_mode=PaymentEnvironmentMode.TEST,
        is_test=True,
        card_number_snapshot_encrypted=None,
        card_last4=None,
        card_holder_snapshot=None,
        card_configured_snapshot=False,
        status=PaymentOrderStatus.CREATED,
        created_at=now,
        expires_at=now + timedelta(hours=24),
    )
    provider = StubZibal()

    async with session_factory() as session:
        session.add(order)
        await session.commit()
        first_order, first_attempt = await start_zibal_checkout(
            session, order_id=order.id, provider=provider, settings=settings, now=now
        )
        second_order, second_attempt = await start_zibal_checkout(
            session, order_id=order.id, provider=provider, settings=settings, now=now
        )
        assert provider.create_calls == 1
        assert first_attempt.id == second_attempt.id
        assert second_order.status == PaymentOrderStatus.PENDING_PAYMENT
        assert first_order.payment_method == "ZIBAL"

        paid_order, paid_attempt, result = await verify_zibal_callback(
            session, track_id="zibal-track-1", provider=provider
        )
        assert result == "test_approved_no_activation"
        assert paid_order.status == PaymentOrderStatus.TEST_APPROVED_NO_ACTIVATION
        assert paid_order.activated_at is None
        assert paid_attempt.status == "PAID"

        repeated_order, repeated_attempt, repeated_result = await verify_zibal_callback(
            session, track_id="zibal-track-1", provider=provider
        )
        assert repeated_result == "success"
        assert repeated_order.activated_at is None
        assert repeated_attempt.id == paid_attempt.id
        assert provider.verify_calls == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_verified_amount_mismatch_requires_reconciliation_and_never_activates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_sqlite_schema(engine, "payment_order", "payment_attempt", "financial_audit_log")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    settings = Settings()
    now = datetime.now(timezone.utc)
    order = PaymentOrder(
        order_number="SHK-260101-MISMATCH", agency_id="legacy-agency", user_id="subject-1",
        plan="quarterly", amount_toman=1_347_000, base_amount_toman=1_347_000,
        payment_method="ZIBAL", environment_mode=PaymentEnvironmentMode.LIVE, is_test=False,
        card_number_snapshot_encrypted=None, card_last4=None, card_holder_snapshot=None,
        card_configured_snapshot=False, status=PaymentOrderStatus.CREATED,
        created_at=now, expires_at=now + timedelta(hours=24),
    )
    provider = StubZibal()
    provider.verified_amount_rial += 1

    async with factory() as session:
        session.add(order)
        await session.commit()
        await start_zibal_checkout(session, order_id=order.id, provider=provider, settings=settings, now=now)
        result_order, attempt, result = await verify_zibal_callback(
            session, track_id="zibal-track-1", provider=provider
        )

        assert result == "reconciliation_required"
        assert result_order.status == PaymentOrderStatus.PENDING_PAYMENT
        assert attempt.status == "RECONCILIATION_REQUIRED"
        assert result_order.activated_at is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_finance_not_paid_resolution_cancels_order_and_late_callback_never_activates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await create_sqlite_schema(engine, "payment_order", "payment_attempt", "financial_audit_log")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    settings = Settings()
    now = datetime.now(timezone.utc)
    order = PaymentOrder(
        order_number="SHK-260101-UNKNOWN", agency_id="legacy-agency", user_id="subject-1",
        plan="quarterly", amount_toman=1_347_000, base_amount_toman=1_347_000,
        payment_method="ZIBAL", environment_mode=PaymentEnvironmentMode.TEST, is_test=True,
        card_number_snapshot_encrypted=None, card_last4=None, card_holder_snapshot=None,
        card_configured_snapshot=False, status=PaymentOrderStatus.CREATED,
        created_at=now, expires_at=now + timedelta(hours=24),
    )
    provider = StubZibal()

    async with factory() as session:
        session.add(order)
        await session.commit()
        _, attempt = await start_zibal_checkout(session, order_id=order.id, provider=provider, settings=settings, now=now)
        cancelled, failed = await confirm_zibal_attempt_not_paid(
            session, attempt_id=attempt.id, actor="finance-admin",
            reason="Checked the merchant portal; this track was not paid.", now=now,
        )
        assert cancelled.status == PaymentOrderStatus.CANCELLED
        assert failed.status == "FAILED"

        late_order, late_attempt, result = await verify_zibal_callback(
            session, track_id="zibal-track-1", provider=provider, now=now
        )
        assert result == "reconciliation_required"
        assert late_order.status == PaymentOrderStatus.CANCELLED
        assert late_order.activated_at is None
        assert late_attempt.status == "RECONCILIATION_REQUIRED"

    await engine.dispose()
