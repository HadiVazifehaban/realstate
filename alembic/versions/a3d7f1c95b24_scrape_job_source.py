"""Add ``scrape_job.source`` so a job names the portal it crawls.

Revision ID: a3d7f1c95b24
Revises: f1a2b3c4d5e6

The pipeline and the job service used to reference Divar by module-level import,
so ``SheypoorClient`` / ``parse_sheypoor_*`` were written and unit-tested but
could never be reached: nothing could tell a job which portal to run. This column
is the routing key for ``app.services.scraper.registry``.

Stored as ``varchar`` rather than a native enum on purpose -- registering a new
source must not require a migration, and an unknown key has to survive as a
readable string instead of failing an INSERT.

Every existing row predates multi-source ingestion and was crawled from Divar,
so the column is added with a server default and backfilled to ``'divar'`` before
the default is dropped: rows written by an older build during a rolling
restart must still be routable.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3d7f1c95b24"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "scrape_job"
COLUMN = "source"
INDEX = "ix_scrape_job_source"


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c["name"] for c in sa.inspect(bind).get_columns(TABLE)}
    if COLUMN not in existing:
        op.add_column(
            TABLE,
            sa.Column(
                COLUMN,
                sa.String(length=32),
                nullable=False,
                server_default="divar",
            ),
        )
    # Idempotent for a partially-applied run.
    op.execute(sa.text(f"UPDATE {TABLE} SET {COLUMN} = 'divar' WHERE {COLUMN} IS NULL"))
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes(TABLE)}
    if INDEX not in indexes:
        op.create_index(INDEX, TABLE, [COLUMN])


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes(TABLE)}
    if INDEX in indexes:
        op.drop_index(INDEX, table_name=TABLE)
    existing = {c["name"] for c in sa.inspect(bind).get_columns(TABLE)}
    if COLUMN in existing:
        op.drop_column(TABLE, COLUMN)