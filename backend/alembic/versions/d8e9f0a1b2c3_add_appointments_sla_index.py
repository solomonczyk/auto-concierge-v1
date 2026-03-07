"""add idx_appointments_sla for SLA unconfirmed query

Revision ID: d8e9f0a1b2c3
Revises: c9d0e1f2a3b4
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_appointments_sla",
        "appointments",
        ["tenant_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_appointments_sla", table_name="appointments")
