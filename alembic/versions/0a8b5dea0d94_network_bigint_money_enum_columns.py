"""network bigint money columns

Revision ID: 0a8b5dea0d94
Revises: b1c2d3e4f5a6
Create Date: 2026-10-18

Commission money columns must hold Toman-scale values, so they move from
INTEGER to BIGINT. Idempotent: uses plain ALTER with a guard.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0a8b5dea0d94'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table, column in [
        ("commission_agreement", "basis_amount"),
        ("commission_allocation", "fixed_amount"),
        ("commission_payment", "amount"),
    ]:
        op.execute(
            sa.text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE BIGINT USING {column}::bigint")
        )


def downgrade() -> None:
    for table, column in [
        ("commission_agreement", "basis_amount"),
        ("commission_allocation", "fixed_amount"),
        ("commission_payment", "amount"),
    ]:
        op.execute(
            sa.text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE INTEGER USING {column}::integer")
        )

