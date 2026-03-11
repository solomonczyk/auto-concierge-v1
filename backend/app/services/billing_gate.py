"""
Billing gate — checks if tenant is allowed to use paid features.

billing_ok = tenant has tariff + tariff active + not blocked.
Currently: tariff_plan presence + tenant operational. No real payment yet.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.models import Tenant
from app.services.tenant_lifecycle_guard import check_tenant_operational_status


async def check_billing_ok(db: AsyncSession, tenant_id: int) -> bool:
    """
    Check if tenant billing is ok: has tariff plan, tariff is active, tenant operational.
    Returns True if tenant can use billing-gated features.
    """
    result = await db.execute(
        select(Tenant).options(joinedload(Tenant.tariff_plan)).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        return False
    operational, _ = await check_tenant_operational_status(db, tenant_id)
    if not operational:
        return False
    if tenant.tariff_plan_id is None:
        return True  # No plan = free tier, allowed
    plan = tenant.tariff_plan
    if not plan:
        return True
    if not getattr(plan, "is_active", True):
        return False
    return True
