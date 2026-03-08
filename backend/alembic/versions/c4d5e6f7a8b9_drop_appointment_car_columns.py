"""drop_appointment_car_columns

Revision ID: c4d5e6f7a8b9
Revises: b3352db051c2
Create Date: 2026-03-08

Drops car_make, car_year, vin from appointments (data already in appointment_auto_snapshots).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b3352db051c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("appointments", "vin")
    op.drop_column("appointments", "car_year")
    op.drop_column("appointments", "car_make")


def downgrade() -> None:
    op.add_column("appointments", sa.Column("car_make", sa.String(100), nullable=True))
    op.add_column("appointments", sa.Column("car_year", sa.Integer(), nullable=True))
    op.add_column("appointments", sa.Column("vin", sa.String(17), nullable=True))
