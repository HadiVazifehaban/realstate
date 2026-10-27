"""Add provider attempts and immutable order snapshots for online billing."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "d9b41e7a2c63"
down_revision: str | None = "4f8b2d1c6a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # These enum types are used for order state and the review's before/after
    # snapshots. The new value is additive; PostgreSQL enum values are retained
    # on downgrade to avoid unsafe enum recreation.
    for enum_name in (
        "payment_order_status",
        "payment_review_previous_status",
        "payment_review_new_status",
    ):
        op.execute(sa.text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS 'pending_payment'"))

    op.alter_column(
        "payment_order", "card_number_snapshot_encrypted",
        existing_type=sa.String(length=512), nullable=True,
    )
    op.alter_column("payment_order", "card_last4", existing_type=sa.String(length=4), nullable=True)
    op.alter_column(
        "payment_order", "card_holder_snapshot",
        existing_type=sa.String(length=255), nullable=True,
    )
    op.add_column("payment_order", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("payment_order", sa.Column("plan_snapshot", sa.JSON(), nullable=True))
    op.create_unique_constraint(
        "uq_payment_order_agency_idempotency", "payment_order", ["agency_id", "idempotency_key"]
    )
    op.create_check_constraint(
        "ck_payment_order_method", "payment_order",
        "payment_method IN ('CARD_TO_CARD', 'ZIBAL')",
    )

    op.create_table(
        "payment_attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        sa.Column("amount_rial", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("gateway_track_id", sa.String(length=64), nullable=True),
        sa.Column("gateway_reference_id", sa.String(length=128), nullable=True),
        sa.Column("payment_url", sa.String(length=2048), nullable=True),
        sa.Column("gateway_result_code", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("response_metadata", sa.JSON(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_inquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_toman > 0 AND amount_rial > 0", name="ck_payment_attempt_positive_amount"),
        sa.ForeignKeyConstraint(["order_id"], ["payment_order.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", "attempt_number", name="uq_payment_attempt_order_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_payment_attempt_idempotency"),
        sa.UniqueConstraint("provider", "gateway_track_id", name="uq_payment_attempt_provider_track"),
    )
    op.create_index("ix_payment_attempt_order_id", "payment_attempt", ["order_id"])
    op.create_index("ix_payment_attempt_status", "payment_attempt", ["status"])
    op.create_index("ix_payment_attempt_gateway_track_id", "payment_attempt", ["gateway_track_id"])
    op.create_index("ix_payment_attempt_gateway_reference_id", "payment_attempt", ["gateway_reference_id"])
    op.create_index("ix_payment_attempt_created_at", "payment_attempt", ["created_at"])
    op.create_index("ix_payment_attempt_status_created", "payment_attempt", ["status", "created_at"])
    op.create_index("ix_payment_attempt_order_created", "payment_attempt", ["order_id", "created_at"])

    # Direct submissions need an immutable billable workspace association for
    # quota accounting. Scraped inventory remains NULL and is never charged.
    op.add_column("property", sa.Column("agency_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(None, "property", "agency", ["agency_id"], ["id"])
    op.create_index("ix_property_agency_id", "property", ["agency_id"])

    op.create_table(
        "subscription_plan",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("price_toman", sa.BigInteger(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("listing_quota", sa.Integer(), nullable=True),
        sa.Column("sms_quota", sa.Integer(), nullable=False),
        sa.Column("regions_quota", sa.Integer(), nullable=False),
        sa.Column("advisor_quota", sa.Integer(), nullable=True),
        sa.Column("is_unlimited", sa.Boolean(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("price_toman >= 0", name="ck_subscription_plan_nonnegative_price"),
        sa.CheckConstraint("duration_days >= 0", name="ck_subscription_plan_nonnegative_duration"),
        sa.CheckConstraint("listing_quota IS NULL OR listing_quota >= 0", name="ck_subscription_plan_listing_quota"),
        sa.CheckConstraint("sms_quota >= 0 AND regions_quota >= 0", name="ck_subscription_plan_quotas"),
        sa.CheckConstraint("advisor_quota IS NULL OR advisor_quota >= 0", name="ck_subscription_plan_advisor_quota"),
        sa.CheckConstraint("is_unlimited OR listing_quota IS NOT NULL", name="ck_subscription_plan_unlimited_explicit"),
        sa.CheckConstraint("is_unlimited OR advisor_quota IS NOT NULL", name="ck_subscription_plan_advisor_unlimited_explicit"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscription_plan_is_active", "subscription_plan", ["is_active"])
    op.create_index("ix_subscription_plan_active_sort", "subscription_plan", ["is_active", "sort_order"])
    op.create_table(
        "zibal_gateway_configuration",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("merchant_ciphertext", sa.Text(), nullable=True),
        sa.Column("merchant_last4", sa.String(length=4), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("test_mode", sa.Boolean(), nullable=False),
        sa.Column("callback_url", sa.String(length=2048), nullable=False),
        sa.Column("result_url", sa.String(length=2048), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_zibal_gateway_configuration_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    plans = sa.table(
        "subscription_plan",
        sa.column("id", sa.String()), sa.column("title", sa.String()),
        sa.column("description", sa.String()), sa.column("price_toman", sa.BigInteger()),
        sa.column("duration_days", sa.Integer()), sa.column("listing_quota", sa.Integer()),
        sa.column("sms_quota", sa.Integer()), sa.column("regions_quota", sa.Integer()),
        sa.column("advisor_quota", sa.Integer()), sa.column("is_unlimited", sa.Boolean()),
        sa.column("features", sa.JSON()), sa.column("is_active", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
    )
    op.bulk_insert(plans, [
        {"id":"free", "title":"پایه رایگان", "description":"پلن پایهٔ رایگان شکارچی", "price_toman":0, "duration_days":30, "listing_quota":3, "sms_quota":0, "regions_quota":0, "advisor_quota":1, "is_unlimited":False, "features":["AVM پایه"], "is_active":True, "sort_order":0},
        {"id":"monthly", "title":"برنز ماهانه", "description":"اشتراک یک‌ماهه", "price_toman":499000, "duration_days":30, "listing_quota":50, "sms_quota":30, "regions_quota":1, "advisor_quota":3, "is_unlimited":False, "features":[], "is_active":True, "sort_order":1},
        {"id":"quarterly", "title":"نقره‌ای فصلی", "description":"اشتراک سه‌ماهه", "price_toman":1347000, "duration_days":90, "listing_quota":150, "sms_quota":100, "regions_quota":2, "advisor_quota":8, "is_unlimited":False, "features":[], "is_active":True, "sort_order":2},
        {"id":"yearly", "title":"طلایی سالانه", "description":"اشتراک یک‌ساله", "price_toman":4790000, "duration_days":365, "listing_quota":None, "sms_quota":500, "regions_quota":1000, "advisor_quota":None, "is_unlimited":True, "features":["PDF تحلیلی AVM", "تیک آبی اعتبارسنجی", "مدیر حساب اختصاصی"], "is_active":True, "sort_order":3},
    ])


def downgrade() -> None:
    bind = op.get_bind()
    has_attempts = bind.execute(sa.text("SELECT EXISTS (SELECT 1 FROM payment_attempt)")).scalar()
    has_online_orders = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM payment_order WHERE payment_method = 'ZIBAL' "
        "OR card_number_snapshot_encrypted IS NULL OR card_last4 IS NULL OR card_holder_snapshot IS NULL)"
    )).scalar()
    has_scoped_properties = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM property WHERE agency_id IS NOT NULL)"
    )).scalar()
    has_customized_plans = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM subscription_plan WHERE "
        "id NOT IN ('free','monthly','quarterly','yearly') OR updated_at > created_at)"
    )).scalar()
    has_zibal_configuration = bind.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM zibal_gateway_configuration)"
    )).scalar()
    if has_attempts or has_online_orders or has_scoped_properties or has_customized_plans or has_zibal_configuration:
        raise RuntimeError("Cannot downgrade while online payments, configured credentials, workspace-scoped listings, or customized plans exist.")

    op.drop_table("zibal_gateway_configuration")
    op.drop_index("ix_subscription_plan_active_sort", table_name="subscription_plan")
    op.drop_index("ix_subscription_plan_is_active", table_name="subscription_plan")
    op.drop_table("subscription_plan")
    op.drop_index("ix_property_agency_id", table_name="property")
    op.drop_constraint("property_agency_id_fkey", "property", type_="foreignkey")
    op.drop_column("property", "agency_id")
    for name in (
        "ix_payment_attempt_order_created",
        "ix_payment_attempt_status_created",
        "ix_payment_attempt_created_at",
        "ix_payment_attempt_gateway_reference_id",
        "ix_payment_attempt_gateway_track_id",
        "ix_payment_attempt_status",
        "ix_payment_attempt_order_id",
    ):
        op.drop_index(name, table_name="payment_attempt")
    op.drop_table("payment_attempt")
    op.drop_constraint("ck_payment_order_method", "payment_order", type_="check")
    op.drop_constraint("uq_payment_order_agency_idempotency", "payment_order", type_="unique")
    op.drop_column("payment_order", "plan_snapshot")
    op.drop_column("payment_order", "idempotency_key")
    op.alter_column(
        "payment_order", "card_holder_snapshot",
        existing_type=sa.String(length=255), nullable=False,
    )
    op.alter_column("payment_order", "card_last4", existing_type=sa.String(length=4), nullable=False)
    op.alter_column(
        "payment_order", "card_number_snapshot_encrypted",
        existing_type=sa.String(length=512), nullable=False,
    )
