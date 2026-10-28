"""Prepare the dark-mode public publication contract (not run automatically)."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "1c7e9a2b4d60"
down_revision: str | None = "f2a8c1d7b904"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Types are created explicitly with checkfirst above; prevent SQLAlchemy
    # from emitting a second CREATE TYPE while creating tables on a DB whose
    # metadata bootstrap already registered the enum.
    consent_status = postgresql.ENUM("NOT_GIVEN", "GIVEN", "REVOKED", name="publication_consent_status", create_type=False)
    review_status = postgresql.ENUM("PENDING", "APPROVED", "REJECTED", name="publication_review_status", create_type=False)
    media_review_status = postgresql.ENUM("PENDING", "APPROVED", "REJECTED", name="media_publication_review_status", create_type=False)
    audit_event = postgresql.ENUM(
        "CONSENT_GIVEN", "CONSENT_REVOKED", "SUBMITTED", "APPROVED", "REJECTED",
        "MEDIA_APPROVED", "MEDIA_REJECTED", "SCHEDULED", "UNPUBLISHED", "EXPIRED",
        name="publication_audit_event", create_type=False,
    )
    bind = op.get_bind()
    for enum in (consent_status, review_status, media_review_status, audit_event):
        enum.create(bind, checkfirst=True)

    op.create_unique_constraint(
        "uq_property_media_property_pair", "property_media", ["property_id", "id"]
    )
    op.create_table(
        "property_publication",
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("consent_status", consent_status, nullable=False, server_default="NOT_GIVEN"),
        sa.Column("consent_actor_subject", sa.String(255), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_version", sa.String(128), nullable=True),
        sa.Column("review_status", review_status, nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by_subject", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note_private", sa.Text(), nullable=True),
        sa.Column("publish_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publish_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_subject", sa.String(255), nullable=True),
        sa.Column("revocation_reason", sa.String(512), nullable=True),
        sa.Column("sanitized_title", sa.Text(), nullable=True),
        sa.Column("sanitized_description", sa.Text(), nullable=True),
        sa.Column("content_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_reviewed_by_subject", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("property_id"),
        sa.ForeignKeyConstraint(["property_id"], ["property.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("public_id", name="uq_property_publication_public_id"),
        sa.CheckConstraint(
            "publish_ends_at IS NULL OR publish_starts_at IS NULL OR publish_ends_at > publish_starts_at",
            name="ck_property_publication_valid_window",
        ),
    )
    op.create_index(
        "ix_property_publication_review_window", "property_publication",
        ["review_status", "publish_starts_at", "publish_ends_at"],
    )
    op.create_table(
        "property_media_publication",
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("allow_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_status", media_review_status, nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by_subject", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("property_id", "media_id"),
        sa.ForeignKeyConstraint(
            ["property_id", "media_id"],
            ["property_media.property_id", "property_media.id"],
            ondelete="CASCADE", name="fk_media_publication_property_media",
        ),
    )
    op.create_index(
        "ix_media_publication_visibility", "property_media_publication",
        ["property_id", "allow_public", "review_status"],
    )
    op.create_table(
        "property_publication_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("media_publication_id", sa.Uuid(), nullable=True),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("event", audit_event, nullable=False),
        sa.Column("actor_subject", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # Audit history is append-only: deleting a publication must be blocked
        # while evidence exists, rather than cascading away the evidence.
        sa.ForeignKeyConstraint(["publication_id"], ["property_publication.property_id"]),
    )
    op.create_index("ix_publication_audit_publication_created", "property_publication_audit", ["publication_id", "created_at"])
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION publication_audit_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'property_publication_audit is append-only';
        END;
        $$;
        CREATE TRIGGER trg_property_publication_audit_immutable
        BEFORE UPDATE OR DELETE ON property_publication_audit
        FOR EACH ROW EXECUTE FUNCTION publication_audit_immutable();
    """))


def downgrade() -> None:
    bind = op.get_bind()
    populated_tables = (
        "property_publication_audit",
        "property_media_publication",
        "property_publication",
    )
    for table_name in populated_tables:
        exists = bind.execute(
            sa.text(f"SELECT EXISTS (SELECT 1 FROM {table_name})")
        ).scalar()
        if exists:
            raise RuntimeError(
                f"Refusing destructive downgrade while {table_name} rows exist"
            )
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_property_publication_audit_immutable ON property_publication_audit"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS publication_audit_immutable()"))
    op.drop_index("ix_publication_audit_publication_created", table_name="property_publication_audit")
    op.drop_table("property_publication_audit")
    op.drop_index("ix_media_publication_visibility", table_name="property_media_publication")
    op.drop_table("property_media_publication")
    op.drop_index("ix_property_publication_review_window", table_name="property_publication")
    op.drop_table("property_publication")
    op.drop_constraint("uq_property_media_property_pair", "property_media", type_="unique")
    for name in ("publication_audit_event", "media_publication_review_status", "publication_review_status", "publication_consent_status"):
        sa.Enum(name=name).drop(bind, checkfirst=True)
