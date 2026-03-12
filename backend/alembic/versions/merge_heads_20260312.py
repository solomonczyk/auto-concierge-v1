"""merge multiple heads

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2, e7f8a9b0c1d2
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = ("a7b8c9d0e1f2", "e7f8a9b0c1d2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
