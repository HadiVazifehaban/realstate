"""Append-only subscription billing records for manual card-to-card payments."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, CheckConstraint, Column, Index, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import (
    AgencyReferralStatus,
    PaymentEnvironmentMode,
    PaymentOrderStatus,
    PaymentReviewDecision,
    ReferralCreditStatus,
)


class SubscriptionPlan(SQLModel, table=True):
    """Backend-owned editable catalog; orders keep the terms they were sold on."""

    __tablename__ = "subscription_plan"
    __table_args__ = (
        CheckConstraint("price_toman >= 0", name="ck_subscription_plan_nonnegative_price"),
        CheckConstraint("duration_days >= 0", name="ck_subscription_plan_nonnegative_duration"),
        CheckConstraint("listing_quota IS NULL OR listing_quota >= 0", name="ck_subscription_plan_listing_quota"),
        CheckConstraint("sms_quota >= 0 AND regions_quota >= 0", name="ck_subscription_plan_quotas"),
        CheckConstraint("advisor_quota IS NULL OR advisor_quota >= 0", name="ck_subscription_plan_advisor_quota"),
        CheckConstraint("is_unlimited OR listing_quota IS NOT NULL", name="ck_subscription_plan_unlimited_explicit"),
        CheckConstraint("is_unlimited OR advisor_quota IS NOT NULL", name="ck_subscription_plan_advisor_unlimited_explicit"),
        Index("ix_subscription_plan_active_sort", "is_active", "sort_order"),
    )

    id: str = Field(primary_key=True, max_length=32)
    title: str = Field(max_length=128)
    description: str = Field(default="", max_length=1000)
    price_toman: int = Field(ge=0, sa_type=BigInteger)
    duration_days: int = Field(ge=0)
    listing_quota: int | None = Field(default=0)
    sms_quota: int = Field(default=0, ge=0)
    regions_quota: int = Field(default=0, ge=0)
    advisor_quota: int | None = Field(default=0)
    is_unlimited: bool = Field(default=False, nullable=False)
    features: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    is_active: bool = Field(default=True, nullable=False, index=True)
    sort_order: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class ZibalGatewayConfiguration(SQLModel, table=True):
    """Singleton gateway configuration; merchant credential is ciphertext only."""

    __tablename__ = "zibal_gateway_configuration"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_zibal_gateway_configuration_singleton"),
    )

    id: int = Field(default=1, primary_key=True)
    merchant_ciphertext: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    merchant_last4: str = Field(default="", max_length=4)
    enabled: bool = Field(default=False, nullable=False)
    test_mode: bool = Field(default=True, nullable=False)
    callback_url: str = Field(default="", max_length=2048)
    result_url: str = Field(default="http://localhost:3000/dashboard/billing", max_length=2048)
    updated_by: str = Field(default="", max_length=255)
    version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class PaymentOrder(SQLModel, table=True):
    __tablename__ = "payment_order"
    __table_args__ = (
        UniqueConstraint("order_number", name="uq_payment_order_number"),
        UniqueConstraint("agency_id", "idempotency_key", name="uq_payment_order_agency_idempotency"),
        Index("ix_payment_order_agency_created", "agency_id", "created_at"),
        Index("ix_payment_order_status_created", "status", "created_at"),
        CheckConstraint("payment_method IN ('CARD_TO_CARD', 'ZIBAL')", name="ck_payment_order_method"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    order_number: str = Field(max_length=32)
    agency_id: str = Field(index=True, max_length=128)
    user_id: str = Field(index=True, max_length=255)
    plan: str = Field(max_length=32)
    plan_snapshot: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    amount_toman: int = Field(ge=0, sa_type=BigInteger)
    base_amount_toman: int = Field(default=0, ge=0, sa_type=BigInteger)
    discount_percent: int = Field(default=0, ge=0, le=100)
    discount_amount_toman: int = Field(default=0, ge=0, sa_type=BigInteger)
    referral_credit_count: int = Field(default=0, ge=0)
    referral_invoice_applied: bool = Field(default=False, nullable=False)
    idempotency_key: str | None = Field(default=None, max_length=128)
    payment_method: str = Field(default="CARD_TO_CARD", max_length=32)
    environment_mode: PaymentEnvironmentMode = Field(
        default=PaymentEnvironmentMode.TEST,
        sa_column=Column(pg_enum(PaymentEnvironmentMode, "payment_environment_mode"), nullable=False),
    )
    is_test: bool = Field(default=True, nullable=False)
    card_number_snapshot_encrypted: str | None = Field(default=None, max_length=512)
    card_last4: str | None = Field(default=None, max_length=4)
    card_holder_snapshot: str | None = Field(default=None, max_length=255)
    card_configured_snapshot: bool = Field(default=False, nullable=False)
    status: PaymentOrderStatus = Field(
        default=PaymentOrderStatus.AWAITING_TRANSFER,
        sa_column=Column(pg_enum(PaymentOrderStatus, "payment_order_status"), nullable=False),
    )
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))
    expires_at: datetime = Field(sa_column=timestamp_column())
    submitted_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    approved_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    rejected_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    activated_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    version: int = Field(default=1, nullable=False)


class PaymentAttempt(SQLModel, table=True):
    """A provider interaction attached to one shared billing order/invoice."""

    __tablename__ = "payment_attempt"
    __table_args__ = (
        UniqueConstraint("order_id", "attempt_number", name="uq_payment_attempt_order_number"),
        UniqueConstraint("idempotency_key", name="uq_payment_attempt_idempotency"),
        UniqueConstraint("provider", "gateway_track_id", name="uq_payment_attempt_provider_track"),
        Index("ix_payment_attempt_status_created", "status", "created_at"),
        Index("ix_payment_attempt_order_created", "order_id", "created_at"),
        CheckConstraint("amount_toman > 0 AND amount_rial > 0", name="ck_payment_attempt_positive_amount"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    order_id: uuid.UUID = Field(foreign_key="payment_order.id", index=True)
    attempt_number: int = Field(ge=1)
    idempotency_key: str = Field(max_length=128)
    provider: str = Field(default="ZIBAL", max_length=32)
    status: str = Field(default="REQUESTING", max_length=32, index=True)
    amount_toman: int = Field(gt=0, sa_type=BigInteger)
    amount_rial: int = Field(gt=0, sa_type=BigInteger)
    currency: str = Field(default="IRR", max_length=3)
    gateway_track_id: str | None = Field(default=None, max_length=64, index=True)
    gateway_reference_id: str | None = Field(default=None, max_length=128, index=True)
    payment_url: str | None = Field(default=None, max_length=2048)
    gateway_result_code: int | None = Field(default=None)
    failure_code: str | None = Field(default=None, max_length=64)
    response_metadata: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    requested_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    verified_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    last_inquired_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class AgencyReferral(SQLModel, table=True):
    __tablename__ = "agency_referral"
    __table_args__ = (
        UniqueConstraint("referred_agency_id", name="uq_agency_referral_referred"),
        CheckConstraint("referrer_agency_id <> referred_agency_id", name="ck_agency_referral_distinct_agencies"),
        Index("ix_agency_referral_referrer_status", "referrer_agency_id", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    referrer_agency_id: uuid.UUID = Field(foreign_key="agency.id", index=True)
    referred_agency_id: uuid.UUID = Field(foreign_key="agency.id", index=True)
    code_used: str = Field(max_length=16)
    status: AgencyReferralStatus = Field(
        default=AgencyReferralStatus.PENDING,
        sa_column=Column(pg_enum(AgencyReferralStatus, "agency_referral_status"), nullable=False),
    )
    source: str = Field(default="professional_registration", max_length=32)
    created_by_subject: str = Field(default="", max_length=255)
    completed_at: datetime | None = Field(default=None, sa_column=timestamp_column(nullable=True))
    completion_order_id: uuid.UUID | None = Field(default=None, foreign_key="payment_order.id", index=True)
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))


class ReferralCredit(SQLModel, table=True):
    __tablename__ = "referral_credit"
    __table_args__ = (
        UniqueConstraint("referral_id", name="uq_referral_credit_referral"),
        CheckConstraint("percent > 0 AND percent <= 20", name="ck_referral_credit_percent"),
        Index("ix_referral_credit_agency_status", "agency_id", "status"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    agency_id: uuid.UUID = Field(foreign_key="agency.id", index=True)
    referral_id: uuid.UUID = Field(unique=True, foreign_key="agency_referral.id", index=True)
    status: ReferralCreditStatus = Field(
        default=ReferralCreditStatus.AVAILABLE,
        sa_column=Column(pg_enum(ReferralCreditStatus, "referral_credit_status"), nullable=False),
    )
    percent: int = Field(ge=1, le=20)
    reserved_order_id: uuid.UUID | None = Field(default=None, foreign_key="payment_order.id", index=True)
    consumed_order_id: uuid.UUID | None = Field(default=None, foreign_key="payment_order.id", index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class PaymentReceipt(SQLModel, table=True):
    __tablename__ = "payment_receipt"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payment_receipt_order"),
        UniqueConstraint("sha256", "order_id", name="uq_payment_receipt_hash_order"),
        UniqueConstraint("transfer_tracking_number", name="uq_payment_receipt_tracking"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    order_id: uuid.UUID = Field(foreign_key="payment_order.id", index=True)
    storage_key: str = Field(max_length=255)
    original_filename: str = Field(max_length=255)
    content_type: str = Field(max_length=64)
    file_size: int = Field(ge=1)
    sha256: str = Field(max_length=64, index=True)
    transfer_tracking_number: str = Field(max_length=128, index=True)
    transfer_datetime: datetime = Field(sa_column=timestamp_column())
    uploader_user_id: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class PaymentReview(SQLModel, table=True):
    __tablename__ = "payment_review"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    order_id: uuid.UUID = Field(foreign_key="payment_order.id", index=True)
    reviewer_user_id: str = Field(max_length=255, index=True)
    decision: PaymentReviewDecision = Field(
        sa_column=Column(pg_enum(PaymentReviewDecision, "payment_review_decision"), nullable=False)
    )
    reason: str = Field(default="", max_length=2000)
    previous_status: PaymentOrderStatus = Field(
        sa_column=Column(pg_enum(PaymentOrderStatus, "payment_review_previous_status"), nullable=False)
    )
    new_status: PaymentOrderStatus = Field(
        sa_column=Column(pg_enum(PaymentOrderStatus, "payment_review_new_status"), nullable=False)
    )
    is_test_review: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))


class FinancialAuditLog(SQLModel, table=True):
    __tablename__ = "financial_audit_log"
    __table_args__ = (Index("ix_financial_audit_entity", "entity_type", "entity_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    actor_user_id: str = Field(max_length=255, index=True)
    actor_role: str = Field(max_length=128)
    action: str = Field(max_length=128, index=True)
    entity_type: str = Field(max_length=64)
    entity_id: uuid.UUID = Field(index=True)
    before_data: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    after_data: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    request_id: str = Field(default="", max_length=128)
    ip_address: str = Field(default="", max_length=64)
    user_agent: str = Field(default="", max_length=512)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))


class AgencySubscription(SQLModel, table=True):
    __tablename__ = "agency_subscription"
    __table_args__ = (Index("ix_agency_subscription_active", "agency_id", "status", "expires_at"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    agency_id: str = Field(index=True, max_length=128)
    plan: str = Field(max_length=32)
    status: str = Field(default="active", max_length=32, index=True)
    starts_at: datetime = Field(sa_column=timestamp_column())
    expires_at: datetime = Field(sa_column=timestamp_column(index=True))
    listing_quota: int | None = Field(default=3)
    sms_quota: int = Field(default=0)
    regions_quota: int = Field(default=0)
    advisor_quota: int | None = Field(default=1)
    is_unlimited: bool = Field(default=False, nullable=False)
    created_by_order_id: uuid.UUID | None = Field(default=None, foreign_key="payment_order.id", index=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class AgencyWallet(SQLModel, table=True):
    __tablename__ = "agency_wallet"
    __table_args__ = (UniqueConstraint("agency_id", name="uq_agency_wallet_agency"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    agency_id: str = Field(max_length=128)
    balance_toman: int = Field(default=0, ge=0, sa_type=BigInteger)
    updated_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column())


class WalletTransaction(SQLModel, table=True):
    __tablename__ = "wallet_transaction"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_wallet_transaction_idempotency"),
        Index("ix_wallet_transaction_agency_created", "agency_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    agency_id: str = Field(index=True, max_length=128)
    amount_toman: int = Field(sa_type=BigInteger)
    transaction_type: str = Field(max_length=64)
    reference_id: str = Field(default="", max_length=255)
    idempotency_key: str = Field(max_length=128)
    created_at: datetime = Field(default_factory=utcnow, sa_column=timestamp_column(index=True))
