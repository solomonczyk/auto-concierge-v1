"""add idx_appointments_sla_new partial index for SLA unconfirmed query

Revision ID: e8f9a0b1c2d3
Revises: d8e9f0a1b2c3
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_appointments_sla_new",
        "appointments",
        ["tenant_id", "created_at"],
        postgresql_where=text("status = 'NEW'"),
    )


def downgrade() -> None:
    op.drop_index("idx_appointments_sla_new", table_name="appointments")
