"""add audit_logs and soft delete (deleted_at, deleted_by)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("payload_before", sa.JSON(), nullable=True),
        sa.Column("payload_after", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(30), nullable=False, server_default="api"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_entity_type_entity_id", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # 2. Add soft delete columns to appointments
    op.add_column("appointments", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("appointments", sa.Column("deleted_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_appointments_deleted_by",
        "appointments",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Add soft delete columns to clients
    op.add_column("clients", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("deleted_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_clients_deleted_by",
        "clients",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_clients_deleted_by", "clients", type_="foreignkey")
    op.drop_column("clients", "deleted_by")
    op.drop_column("clients", "deleted_at")

    op.drop_constraint("fk_appointments_deleted_by", "appointments", type_="foreignkey")
    op.drop_column("appointments", "deleted_by")
    op.drop_column("appointments", "deleted_at")

    op.drop_index("ix_audit_logs_created_at", "audit_logs")
    op.drop_index("ix_audit_logs_entity_type_entity_id", "audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", "audit_logs")
    op.drop_table("audit_logs")
