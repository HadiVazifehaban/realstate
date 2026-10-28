"""Add ``DELTA`` to the ``property_source`` enum.

Revision ID: b7e2c9a4d103
Revises: a3d7f1c95b24

Delta joins Divar and Sheypoor as a crawlable portal (see
``app/services/scraper/delta_client.py``). ``property.source`` is a *native*
PostgreSQL enum, so adding the member to ``PropertySource`` in Python is not
enough -- an insert carrying ``DELTA`` is rejected by the database with
``invalid input value for enum property_source`` until the type itself carries
the label.

PostgreSQL cannot add a value inside a transaction (no ``ALTER TYPE ... ADD
VALUE`` before PG 12 without an explicit non-transactional block), so the type
is renamed out of the way, recreated with the full label set, and every column is
cast over -- the same swap ``e2f4a6b8c9d1`` used. Existing rows keep their value
because every prior label survives.

Downgrade folds ``DELTA`` rows onto ``DIVAR``: the physical listing is still in
the node, only its provenance badge is lost. Deleting them instead would take
live listings with them.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "b7e2c9a4d103"
down_revision: Union[str, None] = "a3d7f1c95b24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Must stay in step with ``PropertySource`` in ``app/models/enums.py``.
SOURCE_LABELS = (
    "INTERNAL_USER", "INTERNAL_AGENCY", "SHEYPOOR", "DIVAR", "DELTA",
    "MLS_IMPORT", "DIVAR_KENAR", "DIVAR_SCRAPER", "MANUAL_OFFICE",
)
#: Label set without Delta, for :func:`downgrade`.
PRE_DELTA_LABELS = (
    "INTERNAL_USER", "INTERNAL_AGENCY", "SHEYPOOR", "DIVAR",
    "MLS_IMPORT", "DIVAR_KENAR", "DIVAR_SCRAPER", "MANUAL_OFFICE",
)


def _swap_enum(labels: tuple[str, ...]) -> None:
    """Recreate ``property_source`` with ``labels``, migrating rows across.

    The rename target is dropped first: a previous partial run may have left a
    ``_old`` type behind, and ``ALTER TYPE ... RENAME`` fails outright if the
    destination name is already taken.
    """
    bind = op.get_bind()
    old_name = "property_source_old"

    if context.is_offline_mode():
        values = ", ".join("'" + label.replace("'", "''") + "'" for label in labels)
        op.execute('ALTER TYPE property_source RENAME TO "property_source_old"')
        op.execute(f'CREATE TYPE property_source AS ENUM ({values})')
        op.execute(
            "ALTER TABLE property ALTER COLUMN source "
            "TYPE property_source USING source::text::property_source"
        )
        op.execute('DROP TYPE "property_source_old"')
        return

    # A partial run may have left the type already renamed out of the way.
    exists = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'property_source'")
    ).first()
    already_swapped = exists is None

    postgresql.ENUM(name=old_name).drop(bind, checkfirst=True)
    if not already_swapped:
        op.execute('ALTER TYPE property_source RENAME TO "property_source_old"')
    postgresql.ENUM(*labels, name="property_source").create(bind, checkfirst=True)
    op.execute(
        "ALTER TABLE property ALTER COLUMN source "
        "TYPE property_source USING source::text::property_source"
    )
    postgresql.ENUM(name=old_name).drop(bind, checkfirst=True)


def upgrade() -> None:
    _swap_enum(SOURCE_LABELS)


def downgrade() -> None:
    op.execute("UPDATE property SET source = 'DIVAR'::property_source "
               "WHERE source = 'DELTA'::property_source")
    _swap_enum(PRE_DELTA_LABELS)
