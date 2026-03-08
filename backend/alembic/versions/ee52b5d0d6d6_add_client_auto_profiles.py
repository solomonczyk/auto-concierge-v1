"""add_client_auto_profiles

Revision ID: ee52b5d0d6d6
Revises: a6b7c8d9e0f1
Create Date: 2026-03-08 15:08:11.939699

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ee52b5d0d6d6'
down_revision: Union[str, Sequence[str], None] = 'a6b7c8d9e0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'client_auto_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('car_make', sa.String(length=100), nullable=True),
        sa.Column('car_year', sa.Integer(), nullable=True),
        sa.Column('vin', sa.String(length=17), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_client_auto_profiles_client_id'),
        'client_auto_profiles',
        ['client_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_client_auto_profiles_client_id'),
        table_name='client_auto_profiles',
    )
    op.drop_table('client_auto_profiles')
