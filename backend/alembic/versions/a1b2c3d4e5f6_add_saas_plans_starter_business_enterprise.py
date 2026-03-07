"""Add SaaS plans: starter, business, enterprise

Revision ID: a1b2c3d4e5f6
Revises: f9a0b1c2d3e4
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Insert starter, business, enterprise if not exist (split to avoid asyncpg param type ambiguity)
    for name, max_appt, max_shops in [
        ("starter", 50, 1),
        ("business", 500, 5),
        ("enterprise", 5000, 50),
    ]:
        exists = conn.execute(
            sa.text("SELECT 1 FROM tariff_plans WHERE name = :n"),
            {"n": name},
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO tariff_plans (name, max_appointments, max_shops, is_active) "
                    "VALUES (:n, :ma, :ms, true)"
                ),
                {"n": name, "ma": max_appt, "ms": max_shops},
            )
    # Migrate existing tenants: free->starter, standard->business, pro->enterprise
    conn.execute(
        sa.text("""
            UPDATE tenants SET tariff_plan_id = (SELECT id FROM tariff_plans WHERE name = 'starter' LIMIT 1)
            WHERE tariff_plan_id IN (SELECT id FROM tariff_plans WHERE name = 'free')
        """)
    )
    conn.execute(
        sa.text("""
            UPDATE tenants SET tariff_plan_id = (SELECT id FROM tariff_plans WHERE name = 'business' LIMIT 1)
            WHERE tariff_plan_id IN (SELECT id FROM tariff_plans WHERE name = 'standard')
        """)
    )
    conn.execute(
        sa.text("""
            UPDATE tenants SET tariff_plan_id = (SELECT id FROM tariff_plans WHERE name = 'enterprise' LIMIT 1)
            WHERE tariff_plan_id IN (SELECT id FROM tariff_plans WHERE name = 'pro')
        """)
    )


def downgrade() -> None:
    # No-op: we don't remove starter/business/enterprise to avoid breaking tenants
    pass
