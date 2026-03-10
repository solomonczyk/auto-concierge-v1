"""add telegram_bots table

Revision ID: 8f17c9812574
Revises: d5e6f8a9b0c1
Create Date: 2026-03-10 05:58:37.857156

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8f17c9812574'
down_revision: Union[str, Sequence[str], None] = 'd5e6f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('telegram_bots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('bot_token', sa.String(), nullable=False),
        sa.Column('bot_username', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bot_token')
    )
    op.create_index(op.f('ix_telegram_bots_tenant_id'), 'telegram_bots', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_telegram_bots_tenant_id'), table_name='telegram_bots')
    op.drop_table('telegram_bots')
