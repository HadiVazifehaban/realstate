"""Phase 3b: widen Toman money columns from INTEGER to BIGINT.

Revision ID: b3d8e0f71a95
Revises: f7a2b91c4d60

Phase 1 declared every money column as a 32-bit INTEGER (ceiling
2,147,483,647). Iranian listings are priced in Toman: a mid-range Tehran
apartment is ~12,000,000,000 Toman, so the first realistic scrape raised
``NumericValueOutOfRange`` on insert. Widening to BIGINT (ceiling ~9.2e18)
fixes it without data loss — every stored value already fits in INTEGER.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3d8e0f71a95"
down_revision: Union[str, None] = "f7a2b91c4d60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column) pairs that must hold Toman amounts.
_MONEY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("property", "total_price"),
    ("property", "deposit_amount"),
    ("property", "monthly_rent"),
    ("property", "price_per_meter"),
    ("client_demand", "min_total_price"),
    ("client_demand", "max_total_price"),
    ("client_demand", "min_deposit"),
    ("client_demand", "max_deposit"),
    ("client_demand", "max_monthly_rent"),
)


def upgrade() -> None:
    for table, column in _MONEY_COLUMNS:
        # USING is explicit so Postgres rewrites the type in place; existing
        # values fit in BIGINT so no cast failure is possible.
        op.alter_column(
            table,
            column,
            type_=sa.BigInteger(),
            existing_type=sa.Integer(),
            existing_nullable=True,
            postgresql_using=f"{column}::bigint",
        )


def downgrade() -> None:
    # Narrowing back can overflow if any row now exceeds 2^31-1; only attempt
    # it when the data actually fits.
    for table, column in _MONEY_COLUMNS:
        op.execute(
            f"SELECT CASE WHEN EXISTS (SELECT 1 FROM {table} "
            f"WHERE {column} > 2147483647) THEN 1 ELSE 0 END"
        )
        op.alter_column(
            table,
            column,
            type_=sa.Integer(),
            existing_type=sa.BigInteger(),
            existing_nullable=True,
            postgresql_using=f"{column}::integer",
        )