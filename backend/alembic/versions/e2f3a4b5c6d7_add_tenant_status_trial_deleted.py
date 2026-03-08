"""add TRIAL and DELETED to tenantstatus enum

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-03-07

"""
from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE tenantstatus ADD VALUE IF NOT EXISTS 'trial'")
    op.execute("ALTER TYPE tenantstatus ADD VALUE IF NOT EXISTS 'deleted'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # Downgrade is a no-op; new tenants would need manual migration.
    pass
