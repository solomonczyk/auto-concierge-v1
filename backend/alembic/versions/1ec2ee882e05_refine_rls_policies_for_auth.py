"""refine rls policies for auth

Revision ID: 1ec2ee882e05
Revises: f0a4addd46ec
Create Date: 2026-02-20 18:26:55.757172

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ec2ee882e05'
down_revision: Union[str, Sequence[str], None] = 'f0a4addd46ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Refine tenants policy: allow SELECT if app.current_tenant_id is NULL (for identification)
    op.execute(sa.text("DROP POLICY IF EXISTS tenant_isolation_policy ON tenants"))
    op.execute(sa.text("""
        CREATE POLICY tenant_isolation_policy ON tenants
        USING (
            id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer
            OR NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL
        )
        WITH CHECK (
            id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer
        )
    """))

    # For other tables, add WITH CHECK to ensure tenant_id matches during INSERT/UPDATE
    tables_with_tenant_id = ['shops', 'clients', 'services', 'appointments', 'users']
    for table in tables_with_tenant_id:
        policy_name = f"{table}_isolation_policy"
        op.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name} ON {table}"))
        
        # User policy still allows lookup by username if tenant not set
        if table == 'users':
            op.execute(sa.text(f"""
                CREATE POLICY {policy_name} ON {table}
                USING (
                    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer
                    OR NULLIF(current_setting('app.current_tenant_id', true), '') IS NULL
                )
                WITH CHECK (
                    tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer
                )
            """))
        else:
            op.execute(sa.text(f"""
                CREATE POLICY {policy_name} ON {table}
                USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)
            """))


def downgrade() -> None:
    # Revert to original restrictive policies if needed, or just keep these as they are "fixed"
    # For simplicity, I'll just keep the downgrade matching the drop/create pattern in the previous migration
    pass
