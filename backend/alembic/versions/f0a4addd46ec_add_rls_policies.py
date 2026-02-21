"""add rls policies

Revision ID: f0a4addd46ec
Revises: 7a15984c2813
Create Date: 2026-02-20 18:25:56.482725

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0a4addd46ec'
down_revision: Union[str, Sequence[str], None] = '7a15984c2813'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    tables = ['tenants', 'shops', 'clients', 'services', 'appointments', 'users']
    
    for table in tables:
        # Enable RLS and force it even for table owners (optional but safer)
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

    # Policy for tenants: can only see own tenant record
    op.execute(sa.text("""
        CREATE POLICY tenant_isolation_policy ON tenants
        USING (id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)
    """))

    # Standard policy for tenant-owned tables
    for table in ['shops', 'clients', 'services', 'appointments']:
        op.execute(sa.text(f"""
            CREATE POLICY {table}_isolation_policy ON {table}
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)
        """))

    # Policy for users: allow access if tenant matches, 
    # OR if app.current_tenant_id is not set (to allow login lookup by username)
    op.execute(sa.text("""
        CREATE POLICY users_isolation_policy ON users
        USING (
            NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL 
            OR tenant_id = current_setting('app.current_tenant_id', true)::integer
        )
    """))


def downgrade() -> None:
    """Downgrade schema."""
    tables = ['tenants', 'shops', 'clients', 'services', 'appointments', 'users']
    
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_policy ON tenants"))
    op.execute(sa.text("DROP POLICY IF EXISTS shops_isolation_policy ON shops"))
    op.execute(sa.text("DROP POLICY IF EXISTS clients_isolation_policy ON clients"))
    op.execute(sa.text("DROP POLICY IF EXISTS services_isolation_policy ON services"))
    op.execute(sa.text("DROP POLICY IF EXISTS appointments_isolation_policy ON appointments"))
    op.execute(sa.text("DROP POLICY IF EXISTS users_isolation_policy ON users"))

    for table in tables:
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
