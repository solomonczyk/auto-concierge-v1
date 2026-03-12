"""
SaaS onboarding finalization — when onboarding is complete, transition tenant to operational state.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Tenant, TenantStatus
from app.services.tenant_readiness_service import compute_onboarding_state


async def finalize_tenant_onboarding(db: AsyncSession, tenant_id: int) -> tuple[bool, str]:
    """
    If onboarding is complete (tenant_created, tariff_assigned, bot registered, webhook provisioned,
    readiness_ok), set tenant status to ACTIVE (or TRIAL) and return (True, message).
    Otherwise return (False, reason).
    """
    state = await compute_onboarding_state(db, tenant_id)
    if not state.get("onboarding_complete", False):
        missing = state.get("missing_steps", [])
        return False, f"Onboarding incomplete: missing {', '.join(missing)}"

    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        return False, "Tenant not found"

    if tenant.status in (TenantStatus.ACTIVE, TenantStatus.TRIAL):
        return True, "Tenant already operational"

    tenant.status = TenantStatus.ACTIVE
    await db.commit()
    await db.refresh(tenant)
    return True, "Onboarding finalized; tenant is now ACTIVE"
