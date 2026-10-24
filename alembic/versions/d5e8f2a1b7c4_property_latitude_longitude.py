"""Phase 3b fix: add the scalar latitude/longitude columns on ``property``.

Revision ID: d5e8f2a1b7c4
Revises: a4c1e2b3d4f5

``a4c1e2b3d4f5`` states in its docstring that the geography columns were "added
upstream by the Phase 2/3 migrations", but no migration ever created them --
the assumption was never true. Only the ``location`` geometry existed, while
``app/services/submission.find_nearby`` filters on ``Property.latitude`` and
``app/api/v1/endpoints/properties._summary`` reads it, so the direct-submission
and near-duplicate paths raised ``AttributeError`` at runtime.

This revision adds the two scalar columns (nullable) plus their B-tree indexes,
so the dedup scan and the public projection can filter and sort without
evaluating a geometry expression per row. ``location`` stays the single
authoritative geometry; ``submit_property`` writes all three together.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e8f2a1b7c4"
down_revision: Union[str, None] = "a4c1e2b3d4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("property", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("property", sa.Column("longitude", sa.Float(), nullable=True))
    op.create_index("ix_property_latitude", "property", ["latitude"], unique=False)
    op.create_index("ix_property_longitude", "property", ["longitude"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_property_longitude", table_name="property")
    op.drop_index("ix_property_latitude", table_name="property")
    op.drop_column("property", "longitude")
    op.drop_column("property", "latitude")
