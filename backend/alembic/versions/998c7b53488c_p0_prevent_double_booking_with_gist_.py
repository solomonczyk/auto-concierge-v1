"""p0 prevent double booking with gist exclude

Revision ID: 998c7b53488c
Revises: f7f619a6c648
Create Date: 2026-03-16 14:58:19.613124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '998c7b53488c'
down_revision: Union[str, Sequence[str], None] = 'f7f619a6c648'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Needed for EXCLUDE constraint using equality on int columns (tenant_id/service_id)
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # 2) Prevent double booking (overlapping time ranges) per tenant + service.
    #    '[)' means inclusive start, exclusive end.
    op.execute("""
    ALTER TABLE appointments
    ADD CONSTRAINT appointments_no_overlap
    EXCLUDE USING gist (
        tenant_id WITH =,
        service_id WITH =,
        tstzrange(start_time, end_time, '[)') WITH &&
    )
    WHERE (deleted_at IS NULL);
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_no_overlap")
    # keep extension (safe, used by other constraints) — do not drop
