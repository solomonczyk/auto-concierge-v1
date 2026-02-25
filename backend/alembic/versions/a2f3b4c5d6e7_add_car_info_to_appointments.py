"""add car info fields to appointments

Revision ID: a2f3b4c5d6e7
Revises: 1ec2ee882e05
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2f3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = '1ec2ee882e05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('appointments', sa.Column('car_make', sa.String(100), nullable=True))
    op.add_column('appointments', sa.Column('car_year', sa.Integer(), nullable=True))
    op.add_column('appointments', sa.Column('vin', sa.String(17), nullable=True))


def downgrade() -> None:
    op.drop_column('appointments', 'vin')
    op.drop_column('appointments', 'car_year')
    op.drop_column('appointments', 'car_make')
