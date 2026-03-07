"""drop idx_appointments_sla in favor of partial idx_appointments_sla_new

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("idx_appointments_sla", table_name="appointments")


def downgrade() -> None:
    op.create_index(
        "idx_appointments_sla",
        "appointments",
        ["tenant_id", "status", "created_at"],
    )
