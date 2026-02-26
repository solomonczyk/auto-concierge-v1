"""merge divergent heads

Revision ID: 2e13feb57458
Revises: a2f3b4c5d6e7, c8a31e2b0316
Create Date: 2026-02-26 20:06:16.464806

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e13feb57458'
down_revision: Union[str, Sequence[str], None] = ('a2f3b4c5d6e7', 'c8a31e2b0316')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
