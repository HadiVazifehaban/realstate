"""Phase 2b: extend property_type with the full Divar taxonomy.

Revision ID: c4e19a7d2f83
Revises: b7c41f2a9e03

Divar's taxonomy (see docs/divar_taxonomy.md) includes short-term suites
(سوئیت و اتاق) and industrial/agricultural properties, which have no
counterpart in the Phase 1 enum:

* ``SUITE``      -> suite-apartment / temporary-rent
* ``INDUSTRIAL`` -> buy|rent-industrial-agricultural-property

Postgres cannot drop a single enum value, so ``downgrade()`` is a no-op.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "c4e19a7d2f83"
down_revision: Union[str, None] = "b7c41f2a9e03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum values must be added outside a transaction block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE property_type ADD VALUE IF NOT EXISTS 'SUITE'")
        op.execute("ALTER TYPE property_type ADD VALUE IF NOT EXISTS 'INDUSTRIAL'")


def downgrade() -> None:
    # Postgres cannot remove individual enum values without recreating the
    # type (which would require rewriting every referencing column).
    pass