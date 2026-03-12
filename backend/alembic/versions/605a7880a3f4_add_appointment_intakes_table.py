"""add appointment_intakes table

Revision ID: 605a7880a3f4
Revises: 8f17c9812574
Create Date: 2026-03-10 14:22:25.741440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '605a7880a3f4'
down_revision: Union[str, Sequence[str], None] = '8f17c9812574'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appointment_intakes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("answers_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_appointment_intakes_appointment_id"),
        "appointment_intakes",
        ["appointment_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_appointment_intakes_appointment_id"), table_name="appointment_intakes")
    op.drop_table("appointment_intakes")
