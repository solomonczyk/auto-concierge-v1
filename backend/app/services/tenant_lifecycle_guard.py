"""
Tenant lifecycle guard — reusable check for tenant operational status.

Usage:
  await ensure_tenant_operational(db, tenant_id)  # raises HTTPException if blocked
  await check_tenant_operational_status(db, tenant_id)  # returns (operational: bool, tenant | None)
"""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Tenant, TenantStatus

OPERATIONAL_STATUSES = (TenantStatus.ACTIVE, TenantStatus.TRIAL)
BLOCKED_STATUSES = (TenantStatus.SUSPENDED, TenantStatus.DISABLED, TenantStatus.DELETED, TenantStatus.PENDING)


def _is_operational(s: TenantStatus) -> bool:
    return s in OPERATIONAL_STATUSES


async def check_tenant_operational_status(
    db: AsyncSession, tenant_id: int
) -> tuple[bool, Tenant | None]:
    """
    Check if tenant exists and is operational (ACTIVE or TRIAL).
    Returns (operational, tenant_or_none).
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return False, None
    return _is_operational(tenant.status), tenant


async def ensure_tenant_operational(
    db: AsyncSession, tenant_id: int, *, require_active_only: bool = False
) -> Tenant:
    """
    Ensure tenant exists and is operational. Raises HTTPException if not.
    - 404 if tenant not found
    - 403 with clear detail if SUSPENDED or DISABLED (or DELETED/PENDING)
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    if not _is_operational(tenant.status):
        if tenant.status == TenantStatus.SUSPENDED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт временно приостановлен. Бронирование недоступно.",
            )
        if tenant.status == TenantStatus.DISABLED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт отключен. Бронирование недоступно.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Сервис временно недоступен.",
        )
    return tenant
