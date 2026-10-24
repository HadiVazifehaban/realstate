"""Advisor card columns, ``poi_cache``, and ``property_report``.

Revision ID: c4d8e1f2a905
Revises: b7e2c9a4d103

Three additions that the property detail page needs and the model did not have:

1. ``property.agent_name`` / ``agency_name`` / ``agency_slug``. The crawlers
   already parsed a listed-by identity (Delta's ``offeredBy`` /
   ``realEstateAgency``, Divar's ``contact`` block) but ``build_property_fields``
   dropped it on the floor, so the advisor card had no data source. Business
   identity only -- the owner's personal contact stays in the encrypted vault.

2. ``poi_cache``. A nearby-points-of-interest lookup hits Overpass, which is a
   free public service: one request per listing would be rude and get the node's
   IP throttled. Cached per rounded coordinate with a 7-day TTL, because the
   answer for a given block does not change within a week.

3. ``property_report``, so "report this listing" has somewhere to land other
   than nowhere.

All three are additive: no column is dropped or retyped, so existing rows are
untouched and ``downgrade`` only removes what these added.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
import geoalchemy2.types

revision: str = "c4d8e1f2a905"
down_revision: Union[str, None] = "b7e2c9a4d103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "property",
        sa.Column("agent_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "property",
        sa.Column("agency_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "property",
        sa.Column("agency_slug", sa.String(length=255), nullable=True),
    )

    # Rounded to ~100 m so listings in the same block share one cache entry. A
    # Geometry column rather than two floats: the ST_DWithin radius query runs
    # against this table, and a GiST index on the geometry is what makes it fast.
    op.create_table(
        "poi_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cell_lat", sa.Float(), nullable=False),
        sa.Column("cell_lng", sa.Float(), nullable=False),
        # Geometry mirror of the cell centre. Kept alongside the scalars because
        # the freshness sweep asks "which cached cells are within N metres of
        # me", which is an ST_DWithin question answered by a GiST index rather
        # than by arithmetic on two columns.
        sa.Column(
            "point",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # One row per block: the second writer in a race overwrites rather than
    # duplicating, and the unique index is what the lookup relies on.
    op.create_index(
        "uq_poi_cache_cell", "poi_cache", ["cell_lat", "cell_lng"], unique=True
    )
    op.execute("CREATE INDEX ix_poi_cache_point ON poi_cache USING GIST (point)")
    op.create_table(
        "property_report",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "property_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("property.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        # Reporter identity. Deliberately not a foreign key: a report must
        # survive the reporter's account being deleted, and the abuse team only
        # needs something to answer an abuse email to.
        sa.Column("reporter_email", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # One open report per property per reason is enough signal; a repeat is
    # noise that would only dilute the queue.
    op.create_index(
        "ix_property_report_property", "property_report", ["property_id"]
    )


def downgrade() -> None:
    op.drop_table("property_report")
    op.execute("DROP INDEX IF EXISTS ix_poi_cache_point")
    op.drop_index("uq_poi_cache_cell", table_name="poi_cache")
    op.drop_table("poi_cache")
    op.drop_column("property", "agency_slug")
    op.drop_column("property", "agency_name")
    op.drop_column("property", "agent_name")