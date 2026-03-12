"""add appointment_history event_type and payload for reschedule audit

Revision ID: e7f8a9b0c1d2
Revises: 3306616dacb3
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "3306616dacb3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "appointment_history",
        sa.Column("event_type", sa.String(30), nullable=True, server_default="status_change"),
    )
    op.add_column(
        "appointment_history",
        sa.Column("payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("appointment_history", "payload")
    op.drop_column("appointment_history", "event_type")
