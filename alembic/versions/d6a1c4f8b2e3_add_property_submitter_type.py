"""Add ``property.submitter_type`` — who filed the listing.

Revision ID: d6a1c4f8b2e3
Revises: 9c1d2e3f4a5b

``POST /properties`` hard-coded ``source = MANUAL_OFFICE`` for *every* direct
submission, so a private owner registering their own unit and a broker filing a
client's both landed on the single ``INTERNAL_AGENCY`` bucket (via
``LEGACY_SOURCE_ALIASES``). ``INTERNAL_USER`` existed in the enum, outranked it
at precedence 100 and had a «مالک مستقیم» badge in the UI, but no code path ever
wrote it.

The endpoint also took no ``Principal``, so the node could not tell who had
filed even if it wanted to.

This migration adds the missing dimension as its own column rather than
overloading ``source``, because the two answer different questions:

* ``source`` -- which *channel* the row arrived through (a portal scrape, an MLS
  import, a first-party registration);
* ``submitter_type`` -- what *class of party* pressed submit (شخص حقیقی or
  بنگاه). A broker filing for a private owner is AGENCY while the contacts in
  the encrypted vault remain the owner's; collapsing the two is exactly how a
  listing ends up advertising an office as its own seller.

Nullable, and **no guessing**. A scraped row is not a submission at all, so it
stays NULL rather than being invented into AGENCY. Existing first-party rows are
backfilled from the only evidence they carry -- ``source`` itself -- which is a
real fact about those rows, not an inference:

* ``INTERNAL_USER``      -> ``PERSON``
* ``INTERNAL_AGENCY``    -> ``AGENCY``
* ``MANUAL_OFFICE``      -> ``AGENCY``  (legacy spelling of INTERNAL_AGENCY)
* every other source     -> NULL        (portal scrape / MLS import: no submitter)

The enum is created first, then the column, then the backfill, so a partial run
is replayable and never leaves rows in a state the application cannot read.

Downgrade drops the column; the ``source`` values written by the new code
(``INTERNAL_USER`` / ``INTERNAL_AGENCY``) survive, because both labels have been
in ``property_source`` since ``e2f4a6b8c9d1``.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d6a1c4f8b2e3"
down_revision: Union[str, None] = "9c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: Must stay in step with ``SubmitterType`` in ``app/models/enums.py``.
SUBMITTER_LABELS = ("PERSON", "AGENCY")


def upgrade() -> None:
    bind = op.get_bind()

    # 1) The type. Created on its own so a replay finds it already there.
    postgresql.ENUM(*SUBMITTER_LABELS, name="submitter_type").create(
        bind, checkfirst=True
    )

    # 2) The column. Nullable with no server default: "unknown" is a real state
    #    for a scraped row, and a default would quietly fabricate AGENCY.
    op.add_column(
        "property",
        sa.Column(
            "submitter_type",
            postgresql.ENUM(*SUBMITTER_LABELS, name="submitter_type", create_type=False),
            nullable=True,
            comment="نوع ثبت‌کننده در لحظهٔ ثبت — شخص حقیقی یا بنگاه",
        ),
    )

    # 3) Backfill from the one fact the old rows actually carry. Only the
    #    first-party sources are touched; a portal scrape keeps NULL.
    op.execute(
        """
        UPDATE property
           SET submitter_type = 'PERSON'::submitter_type
         WHERE source IN ('INTERNAL_USER'::property_source)
        """
    )
    op.execute(
        """
        UPDATE property
           SET submitter_type = 'AGENCY'::submitter_type
         WHERE source IN ('INTERNAL_AGENCY'::property_source,
                          'MANUAL_OFFICE'::property_source)
        """
    )


def downgrade() -> None:
    op.drop_column("property", "submitter_type")
    postgresql.ENUM(name="submitter_type").drop(op.get_bind(), checkfirst=True)