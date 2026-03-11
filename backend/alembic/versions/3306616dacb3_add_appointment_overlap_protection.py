"""add appointment overlap protection

Revision ID: 3306616dacb3
Revises: 605a7880a3f4
Create Date: 2026-03-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3306616dacb3"
down_revision: Union[str, Sequence[str], None] = "605a7880a3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.execute(
        """
        ALTER TABLE appointments
        ADD CONSTRAINT appointments_no_overlap_per_shop
        EXCLUDE USING gist (
            shop_id WITH =,
            tstzrange(start_time, end_time, '[)') WITH &&
        )
        WHERE (
            deleted_at IS NULL
            AND status IN ('NEW', 'CONFIRMED', 'IN_PROGRESS')
        )
        """
    )

    op.create_index(
        "idx_appointments_shop_start_end_active",
        "appointments",
        ["shop_id", "start_time", "end_time"],
        unique=False,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND status IN ('NEW', 'CONFIRMED', 'IN_PROGRESS')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "idx_appointments_shop_start_end_active",
        table_name="appointments",
    )

    op.execute(
        """
        ALTER TABLE appointments
        DROP CONSTRAINT IF EXISTS appointments_no_overlap_per_shop
        """
    )
