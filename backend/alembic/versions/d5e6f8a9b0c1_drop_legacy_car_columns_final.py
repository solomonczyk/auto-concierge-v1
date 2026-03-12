"""drop_legacy_car_columns_final

Revision ID: d5e6f8a9b0c1
Revises: c4d5e6f7a8b9
Create Date: 2026-03-08

P1 Leak Migration — final DB cleanup.
Drops legacy car_make, car_year, vin from clients and appointments.
Appointments may already be clean (c4d5); uses IF EXISTS for idempotency.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "d5e6f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LEGACY_COLUMNS = ("car_make", "car_year", "vin")


def _column_exists(conn, table: str, column: str) -> bool:
    dialect = conn.dialect.name
    if dialect == "postgresql":
        r = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        )
        return r.scalar() is not None
    if dialect == "sqlite":
        r = conn.execute(text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in r.fetchall())
    # fallback: assume exists
    return True


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    for table in ("clients", "appointments"):
        for col in LEGACY_COLUMNS:
            if dialect == "postgresql":
                op.execute(text(f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{col}"'))
            else:
                if _column_exists(conn, table, col):
                    op.drop_column(table, col)


def downgrade() -> None:
    op.add_column("clients", sa.Column("car_make", sa.String(100), nullable=True))
    op.add_column("clients", sa.Column("car_year", sa.Integer(), nullable=True))
    op.add_column("clients", sa.Column("vin", sa.String(17), nullable=True))
    op.add_column("appointments", sa.Column("car_make", sa.String(100), nullable=True))
    op.add_column("appointments", sa.Column("car_year", sa.Integer(), nullable=True))
    op.add_column("appointments", sa.Column("vin", sa.String(17), nullable=True))
