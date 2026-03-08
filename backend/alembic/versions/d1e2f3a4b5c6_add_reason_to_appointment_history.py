"""add reason to appointment_history

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-03-07

"""
from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointment_history",
        sa.Column("reason", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("appointment_history", "reason")
