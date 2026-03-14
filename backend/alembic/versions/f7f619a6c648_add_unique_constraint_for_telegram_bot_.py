"""add unique constraint for telegram bot username

Revision ID: f7f619a6c648
Revises: b1c2d3e4f5a6
Create Date: 2026-03-14 06:12:35.584441

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7f619a6c648'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_telegram_bots_bot_username",
        "telegram_bots",
        ["bot_username"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_telegram_bots_bot_username",
        "telegram_bots",
        type_="unique",
    )
