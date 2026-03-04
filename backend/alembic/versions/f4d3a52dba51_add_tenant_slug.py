"""add_tenant_slug

Revision ID: f4d3a52dba51
Revises: 2e13feb57458
Create Date: 2026-03-04 14:48:21.274229

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4d3a52dba51'
down_revision: Union[str, Sequence[str], None] = '2e13feb57458'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # slug column added directly in DB migration applied 2026-03-04
    # column already exists in production, autogenerate confirmed no diff
    op.add_column('tenants', sa.Column('slug', sa.String(100), nullable=True))
    op.create_index('ix_tenants_slug', 'tenants', ['slug'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_tenants_slug', table_name='tenants')
    op.drop_column('tenants', 'slug')
