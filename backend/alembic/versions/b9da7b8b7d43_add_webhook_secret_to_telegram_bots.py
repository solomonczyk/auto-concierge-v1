"""add_webhook_secret_to_telegram_bots

Revision ID: b9da7b8b7d43
Revises: 3306616dacb3
Create Date: 2026-03-11 19:45:39.530656

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9da7b8b7d43'
down_revision: Union[str, Sequence[str], None] = '3306616dacb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("telegram_bots", sa.Column("webhook_secret", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("telegram_bots", "webhook_secret")
