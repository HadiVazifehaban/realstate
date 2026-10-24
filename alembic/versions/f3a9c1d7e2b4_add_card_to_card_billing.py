"""Add card-to-card billing, receipts, reviews, audit, subscriptions and wallet ledger."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f3a9c1d7e2b4"
down_revision: Union[str, None] = "0a8b5dea0d94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

payment_environment_mode = postgresql.ENUM("test", "live", name="payment_environment_mode", create_type=False)
payment_order_status = postgresql.ENUM(
    "created", "awaiting_transfer", "receipt_submitted", "under_review",
    "test_approved_no_activation", "approved", "rejected", "expired", "cancelled",
    name="payment_order_status", create_type=False,
)
payment_review_decision = postgresql.ENUM(
    "started", "approved", "rejected", "test_approved", name="payment_review_decision", create_type=False
)
payment_review_previous_status = postgresql.ENUM(
    "created", "awaiting_transfer", "receipt_submitted", "under_review",
    "test_approved_no_activation", "approved", "rejected", "expired", "cancelled",
    name="payment_review_previous_status", create_type=False,
)
payment_review_new_status = postgresql.ENUM(
    "created", "awaiting_transfer", "receipt_submitted", "under_review",
    "test_approved_no_activation", "approved", "rejected", "expired", "cancelled",
    name="payment_review_new_status", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    payment_environment_mode.create(bind, checkfirst=True)
    payment_order_status.create(bind, checkfirst=True)
    payment_review_decision.create(bind, checkfirst=True)
    payment_review_previous_status.create(bind, checkfirst=True)
    payment_review_new_status.create(bind, checkfirst=True)

    op.create_table(
        "payment_order",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_number", sa.String(32), nullable=False),
        sa.Column("agency_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        sa.Column("payment_method", sa.String(32), nullable=False),
        sa.Column("environment_mode", payment_environment_mode, nullable=False),
        sa.Column("is_test", sa.Boolean(), nullable=False),
        sa.Column("card_number_snapshot_encrypted", sa.String(512), nullable=False),
        sa.Column("card_last4", sa.String(4), nullable=False),
        sa.Column("card_holder_snapshot", sa.String(255), nullable=False),
        sa.Column("card_configured_snapshot", sa.Boolean(), nullable=False),
        sa.Column("status", payment_order_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number", name="uq_payment_order_number"),
    )
    op.create_index("ix_payment_order_agency_id", "payment_order", ["agency_id"])
    op.create_index("ix_payment_order_user_id", "payment_order", ["user_id"])
    op.create_index("ix_payment_order_status_created", "payment_order", ["status", "created_at"])
    op.create_index("ix_payment_order_agency_created", "payment_order", ["agency_id", "created_at"])
    op.create_index("ix_payment_order_created_at", "payment_order", ["created_at"])

    op.create_table(
        "payment_receipt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("transfer_tracking_number", sa.String(128), nullable=False),
        sa.Column("transfer_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploader_user_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["payment_order.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_payment_receipt_order"),
        sa.UniqueConstraint("sha256", "order_id", name="uq_payment_receipt_hash_order"),
        sa.UniqueConstraint("transfer_tracking_number", name="uq_payment_receipt_tracking"),
    )
    op.create_index("ix_payment_receipt_order_id", "payment_receipt", ["order_id"])
    op.create_index("ix_payment_receipt_sha256", "payment_receipt", ["sha256"])
    op.create_index("ix_payment_receipt_transfer_tracking_number", "payment_receipt", ["transfer_tracking_number"])

    op.create_table(
        "payment_review",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.String(255), nullable=False),
        sa.Column("decision", payment_review_decision, nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("previous_status", payment_review_previous_status, nullable=False),
        sa.Column("new_status", payment_review_new_status, nullable=False),
        sa.Column("is_test_review", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["payment_order.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_review_order_id", "payment_review", ["order_id"])
    op.create_index("ix_payment_review_reviewer_user_id", "payment_review", ["reviewer_user_id"])
    op.create_index("ix_payment_review_created_at", "payment_review", ["created_at"])

    op.create_table(
        "financial_audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.String(255), nullable=False),
        sa.Column("actor_role", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("before_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_financial_audit_entity", "financial_audit_log", ["entity_type", "entity_id"])
    op.create_index("ix_financial_audit_log_actor_user_id", "financial_audit_log", ["actor_user_id"])
    op.create_index("ix_financial_audit_log_action", "financial_audit_log", ["action"])
    op.create_index("ix_financial_audit_log_entity_id", "financial_audit_log", ["entity_id"])
    op.create_index("ix_financial_audit_log_created_at", "financial_audit_log", ["created_at"])

    op.create_table(
        "agency_subscription",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agency_id", sa.String(128), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("listing_quota", sa.Integer(), nullable=True),
        sa.Column("sms_quota", sa.Integer(), nullable=False),
        sa.Column("regions_quota", sa.Integer(), nullable=False),
        sa.Column("advisor_quota", sa.Integer(), nullable=True),
        sa.Column("is_unlimited", sa.Boolean(), nullable=False),
        sa.Column("created_by_order_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_order_id"], ["payment_order.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agency_subscription_agency_id", "agency_subscription", ["agency_id"])
    op.create_index("ix_agency_subscription_status", "agency_subscription", ["status"])
    op.create_index("ix_agency_subscription_expires_at", "agency_subscription", ["expires_at"])
    op.create_index("ix_agency_subscription_active", "agency_subscription", ["agency_id", "status", "expires_at"])
    op.create_index("ix_agency_subscription_created_by_order_id", "agency_subscription", ["created_by_order_id"])

    op.create_table(
        "agency_wallet",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agency_id", sa.String(128), nullable=False),
        sa.Column("balance_toman", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_id", name="uq_agency_wallet_agency"),
    )
    op.create_table(
        "wallet_transaction",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agency_id", sa.String(128), nullable=False),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        sa.Column("transaction_type", sa.String(64), nullable=False),
        sa.Column("reference_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_wallet_transaction_idempotency"),
    )
    op.create_index("ix_wallet_transaction_agency_id", "wallet_transaction", ["agency_id"])
    op.create_index("ix_wallet_transaction_created_at", "wallet_transaction", ["created_at"])
    op.create_index("ix_wallet_transaction_agency_created", "wallet_transaction", ["agency_id", "created_at"])


def downgrade() -> None:
    for table, index in [
        ("wallet_transaction", "ix_wallet_transaction_agency_created"),
        ("wallet_transaction", "ix_wallet_transaction_created_at"),
        ("wallet_transaction", "ix_wallet_transaction_agency_id"),
        ("agency_subscription", "ix_agency_subscription_created_by_order_id"),
        ("agency_subscription", "ix_agency_subscription_active"),
        ("agency_subscription", "ix_agency_subscription_expires_at"),
        ("agency_subscription", "ix_agency_subscription_status"),
        ("agency_subscription", "ix_agency_subscription_agency_id"),
        ("financial_audit_log", "ix_financial_audit_log_created_at"),
        ("financial_audit_log", "ix_financial_audit_log_entity_id"),
        ("financial_audit_log", "ix_financial_audit_log_action"),
        ("financial_audit_log", "ix_financial_audit_log_actor_user_id"),
        ("financial_audit_log", "ix_financial_audit_entity"),
        ("payment_review", "ix_payment_review_created_at"),
        ("payment_review", "ix_payment_review_reviewer_user_id"),
        ("payment_review", "ix_payment_review_order_id"),
        ("payment_receipt", "ix_payment_receipt_transfer_tracking_number"),
        ("payment_receipt", "ix_payment_receipt_sha256"),
        ("payment_receipt", "ix_payment_receipt_order_id"),
        ("payment_order", "ix_payment_order_created_at"),
        ("payment_order", "ix_payment_order_agency_created"),
        ("payment_order", "ix_payment_order_status_created"),
        ("payment_order", "ix_payment_order_user_id"),
        ("payment_order", "ix_payment_order_agency_id"),
    ]:
        op.drop_index(index, table_name=table)
    for table in ("wallet_transaction", "agency_wallet", "agency_subscription", "financial_audit_log", "payment_review", "payment_receipt", "payment_order"):
        op.drop_table(table)
    bind = op.get_bind()
    payment_review_new_status.drop(bind, checkfirst=True)
    payment_review_previous_status.drop(bind, checkfirst=True)
    payment_review_decision.drop(bind, checkfirst=True)
    payment_order_status.drop(bind, checkfirst=True)
    payment_environment_mode.drop(bind, checkfirst=True)