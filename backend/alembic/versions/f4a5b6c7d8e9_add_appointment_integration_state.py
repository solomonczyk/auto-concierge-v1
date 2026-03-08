"""add appointment integration state

Revision ID: f4a5b6c7d8e9
Revises: e2f3a4b5c6d7
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa

revision = "f4a5b6c7d8e9"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    integration_status = sa.Enum("PENDING", "SUCCESS", "FAILED", name="integrationstatus")
    integration_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "appointments",
        sa.Column(
            "integration_status",
            integration_status,
            nullable=False,
            server_default="SUCCESS",
        ),
    )
    op.add_column(
        "appointments",
        sa.Column("last_integration_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("last_integration_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("appointments", "last_integration_attempt_at")
    op.drop_column("appointments", "last_integration_error")
    op.drop_column("appointments", "integration_status")
    sa.Enum(name="integrationstatus").drop(op.get_bind(), checkfirst=True)
