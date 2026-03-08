"""drop_client_car_columns

Revision ID: a2241caf40b1
Revises: ee52b5d0d6d6
Create Date: 2026-03-08 15:20:14.995932

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a2241caf40b1'
down_revision: Union[str, Sequence[str], None] = 'ee52b5d0d6d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
