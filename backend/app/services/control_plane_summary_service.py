"""
Platform-wide control plane summary — aggregated metrics across all tenants.
Single source of truth for GET /admin/control-plane/summary.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Tenant, TenantStatus
from app.services.tenant_readiness_service import compute_tenant_readiness


async def compute_platform_summary(db: AsyncSession) -> dict:
    """
    Aggregate platform-wide tenant and readiness metrics.
    Returns dict suitable for ControlPlaneSummaryResponse.
    """
    result = await db.execute(select(Tenant).order_by(Tenant.id))
    tenants = result.scalars().all()
    total = len(tenants)

    active_tenants = sum(
        1 for t in tenants
        if t.status in (TenantStatus.ACTIVE, TenantStatus.TRIAL)
    )
    pending_tenants = sum(1 for t in tenants if t.status == TenantStatus.PENDING)
    suspended_tenants = sum(
        1 for t in tenants
        if t.status in (TenantStatus.SUSPENDED, TenantStatus.DISABLED, TenantStatus.DELETED)
    )

    ready_tenants = 0
    not_ready_tenants = 0
    tenants_without_shop = 0
    tenants_without_services = 0
    tenants_without_bot = 0
    tenants_without_webhook = 0

    for t in tenants:
        flags = await compute_tenant_readiness(db, t.id)
        if flags.get("booking_ready"):
            ready_tenants += 1
        else:
            not_ready_tenants += 1
        if not flags.get("shop_configured"):
            tenants_without_shop += 1
        if not flags.get("services_configured"):
            tenants_without_services += 1
        if not flags.get("telegram_bot_registered"):
            tenants_without_bot += 1
        if not flags.get("telegram_webhook_active"):
            tenants_without_webhook += 1

    return {
        "total_tenants": total,
        "active_tenants": active_tenants,
        "pending_tenants": pending_tenants,
        "suspended_tenants": suspended_tenants,
        "ready_tenants": ready_tenants,
        "not_ready_tenants": not_ready_tenants,
        "tenants_without_shop": tenants_without_shop,
        "tenants_without_services": tenants_without_services,
        "tenants_without_bot": tenants_without_bot,
        "tenants_without_webhook": tenants_without_webhook,
    }
