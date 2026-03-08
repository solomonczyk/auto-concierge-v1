"""add_appointment_auto_snapshots

Revision ID: b3352db051c2
Revises: a2241caf40b1
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b3352db051c2"
down_revision: Union[str, Sequence[str], None] = "a2241caf40b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appointment_auto_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("car_make", sa.String(length=100), nullable=True),
        sa.Column("car_year", sa.Integer(), nullable=True),
        sa.Column("vin", sa.String(length=17), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_appointment_auto_snapshots_appointment_id"),
        "appointment_auto_snapshots",
        ["appointment_id"],
        unique=True,
    )

    op.execute(sa.text("""
        INSERT INTO appointment_auto_snapshots (appointment_id, car_make, car_year, vin, created_at, updated_at)
        SELECT id, car_make, car_year, vin, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM appointments
        WHERE car_make IS NOT NULL OR car_year IS NOT NULL OR vin IS NOT NULL
    """))


def downgrade() -> None:
    op.drop_index(
        op.f("ix_appointment_auto_snapshots_appointment_id"),
        table_name="appointment_auto_snapshots",
    )
    op.drop_table("appointment_auto_snapshots")
