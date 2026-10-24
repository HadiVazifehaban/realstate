"""Phase 3b: price history, AVM verdicts and the reverse-geocoding cache.

Revision ID: a4c1e2b3d4f5
Revises: b3d8e0f71a95

Adds three things the direct-submission path needs:

* ``property_price_history`` -- an append-only price timeline per unit, with a
  unique constraint on ``(property_id, new_price, source)`` so a re-ingested
  listing cannot append the same observation twice;
* ``valuation_status`` / ``valuation_*`` columns on ``property`` -- the engine's
  cached verdict, so the agent desk never recomputes it per request;
* ``geo_cache`` -- reverse-geocoded ~50 m grid cells, so a busy office does not
  re-query Neshan for every pin on the same building.

The scalar geography columns (``latitude``/``longitude``) were *not* present at
this revision; ``d5e8f2a1b7c4`` adds them. An earlier draft of this docstring
claimed they already existed upstream, which was never true.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4c1e2b3d4f5"
down_revision: Union[str, None] = "b3d8e0f71a95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(labels: tuple[str, ...], name: str) -> postgresql.ENUM:
    """Create a PG enum explicitly first, so a partial run stays replayable."""
    enum = postgresql.ENUM(*labels, name=name)
    enum.create(op.get_bind(), checkfirst=True)
    return postgresql.ENUM(*labels, name=name, create_type=False)


def upgrade() -> None:
    price_source = _enum(
        ("SCRAPER", "MANUAL", "OWNER", "AVM"), "price_source"
    )
    valuation_status = _enum(
        ("BARGAIN", "FAIR", "OVERPRICED", "UNKNOWN"), "valuation_status"
    )

    op.add_column(
        "property",
        sa.Column("valuation_status", valuation_status, server_default="UNKNOWN", nullable=False),
    )
    op.create_index(
        "ix_property_valuation_status", "property", ["valuation_status"], unique=False
    )
    op.add_column("property", sa.Column("valuation_deviation_pct", sa.Float(), nullable=True))
    op.add_column(
        "property",
        sa.Column("valuation_median_price_per_meter", sa.BigInteger(), nullable=True),
    )
    op.add_column("property", sa.Column("valuation_sample_count", sa.Integer(), nullable=True))
    op.add_column(
        "property",
        sa.Column("valuation_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "property_price_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("previous_price", sa.BigInteger(), nullable=True),
        sa.Column("new_price", sa.BigInteger(), nullable=False),
        sa.Column("price_difference", sa.BigInteger(), nullable=False),
        sa.Column("change_percentage", sa.Float(), nullable=False),
        sa.Column("source", price_source, nullable=False),
        sa.Column("source_ref", sa.String(length=128), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["property_id"], ["property.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["agency_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "property_id", "new_price", "source", name="uq_price_history_row"
        ),
    )
    op.create_index(
        "ix_property_price_history_property_id",
        "property_price_history",
        ["property_id"],
        unique=False,
    )
    op.create_index(
        "ix_property_price_history_recorded_at",
        "property_price_history",
        ["recorded_at"],
        unique=False,
    )

    op.create_table(
        "geo_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("grid_key", sa.String(length=64), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("province", sa.String(length=64), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("district", sa.String(length=128), nullable=False),
        sa.Column("neighborhood", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=512), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_geo_cache_grid_key", "geo_cache", ["grid_key"], unique=True)
    op.create_index("ix_geo_cache_fetched_at", "geo_cache", ["fetched_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_geo_cache_fetched_at", table_name="geo_cache")
    op.drop_index("ix_geo_cache_grid_key", table_name="geo_cache")
    op.drop_table("geo_cache")

    op.drop_index("ix_property_price_history_recorded_at", table_name="property_price_history")
    op.drop_index("ix_property_price_history_property_id", table_name="property_price_history")
    op.drop_table("property_price_history")

    op.drop_index("ix_property_valuation_status", table_name="property")
    op.drop_column("property", "valuation_updated_at")
    op.drop_column("property", "valuation_sample_count")
    op.drop_column("property", "valuation_median_price_per_meter")
    op.drop_column("property", "valuation_deviation_pct")
    op.drop_column("property", "valuation_status")

    postgresql.ENUM(name="valuation_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="price_source").drop(op.get_bind(), checkfirst=True)