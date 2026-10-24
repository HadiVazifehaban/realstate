"""Append-only subscription billing records for manual card-to-card payments."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import pg_enum, timestamp_column, utcnow, uuid_column
from app.models.enums import PaymentEnvironmentMode, PaymentOrderStatus, PaymentReviewDecision


class PaymentOrder(SQLModel, table=True):
    __tablename__ = "payment_order"
    __table_args__ = (
        UniqueConstraint("order_number", name="uq_payment_order_number"),
        Index("ix_payment_order_agency_created", "agency_id", "created_at"),
        Index("ix_payment_order_status_created", "status", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_column=uuid_column())
    order_number: str = Field(max_length=32)
    agency_id: str = Field(index=True, max_length=128)
    user_id: str = Field(index=True, max_length=255)
    plan: str = Field(max_length=32)
    amount_toman: int = Field(ge=0, sa_type=BigInteger)
    payment_method: str = Field(default="CARD_TO_CARD", max_length=32)
    environment_mode: PaymentEnvironmentMode = Field(
        default=PaymentEnvironmentMode.TEST,
        sa_column=Column(pg_enum(PaymentEnvironmentMode, "payment_environment_mode"), nullable=False),
    )
    is_test: bool = Field(default=True, nullable=False)
    card_number_snapshot_encrypted: str = Field(max_length=512)
    card_last4: str = Field(max_length=4)
    card_holder_snapshot: str = Field(max_length=255)
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