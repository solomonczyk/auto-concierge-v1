"""add_webhook_provisioning_fields_to_telegram_bots

Revision ID: f131623d2a13
Revises: b9da7b8b7d43
Create Date: 2026-03-11 20:14:15.922792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f131623d2a13'
down_revision: Union[str, Sequence[str], None] = 'b9da7b8b7d43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "telegram_bots",
        sa.Column("webhook_status", sa.String(32), nullable=False, server_default="not_configured"),
    )
    op.add_column(
        "telegram_bots",
        sa.Column("webhook_last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "telegram_bots",
        sa.Column("webhook_last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("telegram_bots", "webhook_last_synced_at")
    op.drop_column("telegram_bots", "webhook_last_error")
    op.drop_column("telegram_bots", "webhook_status")
