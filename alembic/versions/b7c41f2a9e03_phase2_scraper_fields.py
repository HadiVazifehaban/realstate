"""Phase 2: Divar scraper columns + scrape_job table.

Revision ID: b7c41f2a9e03
Revises: c63691ed7bdc

Adds the autonomous-ingestion fields to ``property``:

* ``external_id``  -- Divar token, globally unique (re-scrape updates).
* ``content_hash`` -- SHA256(city + district + area + floor + rounded_price).
* ``raw_data``     -- raw Divar widget payload (JSONB) for re-processing.

and creates the ``scrape_job`` lifecycle table, plus extends the
``property_source`` enum with the ``DIVAR_SCRAPER`` value.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7c41f2a9e03"
down_revision: Union[str, None] = "c63691ed7bdc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Extend the property_source enum (Postgres native enum).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE property_source ADD VALUE IF NOT EXISTS 'DIVAR_SCRAPER'")

    # 2) New ingestion columns on property.
    op.add_column("property", sa.Column("external_id", sa.String(length=128), nullable=True))
    op.add_column("property", sa.Column("content_hash", sa.String(length=128), nullable=True))
    op.add_column(
        "property",
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        op.f("ix_property_external_id"), "property", ["external_id"], unique=True
    )
    op.create_index(
        op.f("ix_property_content_hash"), "property", ["content_hash"], unique=False
    )

    # 3) Scrape-job lifecycle table.
    op.create_table(
        "scrape_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("SEARCH", "DETAIL", "PHONE", name="scrape_job_kind"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED",
                name="scrape_job_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "trigger",
            sa.Enum("MANUAL", "SCHEDULED", "API", name="scrape_job_trigger"),
            nullable=False,
        ),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("pages_scraped", sa.Integer(), nullable=False),
        sa.Column("items_found", sa.Integer(), nullable=False),
        sa.Column("items_new", sa.Integer(), nullable=False),
        sa.Column("items_duplicate", sa.Integer(), nullable=False),
        sa.Column("items_failed", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(length=1024), nullable=True),
        sa.Column("triggered_by_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["triggered_by_id"], ["agency_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scrape_job_city"), "scrape_job", ["city"], unique=False)
    op.create_index(op.f("ix_scrape_job_status"), "scrape_job", ["status"], unique=False)
    op.create_index(
        op.f("ix_scrape_job_created_at"), "scrape_job", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scrape_job_created_at"), table_name="scrape_job")
    op.drop_index(op.f("ix_scrape_job_status"), table_name="scrape_job")
    op.drop_index(op.f("ix_scrape_job_city"), table_name="scrape_job")
    op.drop_table("scrape_job")
    op.execute("DROP TYPE IF EXISTS scrape_job_trigger")
    op.execute("DROP TYPE IF EXISTS scrape_job_status")
    op.execute("DROP TYPE IF EXISTS scrape_job_kind")

    op.drop_index(op.f("ix_property_content_hash"), table_name="property")
    op.drop_index(op.f("ix_property_external_id"), table_name="property")
    op.drop_column("property", "raw_data")
    op.drop_column("property", "content_hash")
    op.drop_column("property", "external_id")
    # NOTE: Postgres cannot drop a single enum value; DIVAR_SCRAPER stays defined.
