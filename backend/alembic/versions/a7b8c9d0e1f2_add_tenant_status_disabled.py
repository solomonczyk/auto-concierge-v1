"""add DISABLED to tenantstatus enum

Revision ID: a7b8c9d0e1f2
Revises: f131623d2a13
Create Date: 2026-03-11

"""
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f131623d2a13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE tenantstatus ADD VALUE IF NOT EXISTS 'disabled'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # Downgrade is a no-op.
    pass
