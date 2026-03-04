"""add_superadmin_role_nullable_tenant_tenant_settings

Revision ID: e1a2b3c4d5e6
Revises: f4d3a52dba51
Create Date: 2026-03-04 18:00:00.000000

Changes:
- ADD VALUE 'SUPERADMIN' to userrole enum
- ALTER users.tenant_id to be nullable (SUPERADMIN has no tenant)
- CREATE TABLE tenant_settings (per-tenant working hours / slot config)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "f4d3a52dba51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add SUPERADMIN to the existing userrole enum.
    #    IF NOT EXISTS is safe for re-runs / already-applied scenarios.
    op.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SUPERADMIN'"))

    # 2. Make users.tenant_id nullable so SUPERADMIN can exist without a tenant.
    op.alter_column(
        "users",
        "tenant_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 3. Create tenant_settings table for per-tenant work hours / slot config.
    op.create_table(
        "tenant_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("work_start", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("work_end", sa.Integer(), nullable=False, server_default="18"),
        sa.Column("slot_duration", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_settings_tenant_id"),
    )
    op.create_index("ix_tenant_settings_tenant_id", "tenant_settings", ["tenant_id"], unique=True)


def downgrade() -> None:
    # 3. Drop tenant_settings
    op.drop_index("ix_tenant_settings_tenant_id", table_name="tenant_settings")
    op.drop_table("tenant_settings")

    # 2. Restore NOT NULL constraint on users.tenant_id
    #    NOTE: This will FAIL if any SUPERADMIN rows (tenant_id=NULL) exist — remove them first.
    op.alter_column(
        "users",
        "tenant_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # 1. PostgreSQL does not support removing enum values.
    #    The SUPERADMIN enum value remains after downgrade.
    #    To fully remove it: DROP TYPE userrole CASCADE and recreate — destructive, not automated here.
