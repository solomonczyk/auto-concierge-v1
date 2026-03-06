"""add completed_at to appointments

Revision ID: b7c8d9e0f1a2
Revises: 2e13feb57458
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'appointments',
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('appointments', 'completed_at')
