from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import TenantSettings


async def get_tenant_settings(
    db: AsyncSession,
    tenant_id: int,
) -> TenantSettings | None:
    stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_tenant_timezone(
    db: AsyncSession,
    tenant_id: int,
    default_timezone: str = "Europe/Moscow",
) -> str:
    tenant_settings = await get_tenant_settings(db, tenant_id)
    if tenant_settings and tenant_settings.timezone:
        return tenant_settings.timezone
    return default_timezone


async def get_tenant_timezones(
    db: AsyncSession,
    tenant_ids: list[int],
    default_timezone: str = "Europe/Moscow",
) -> dict[int, str]:
    if not tenant_ids:
        return {}

    stmt = select(TenantSettings).where(TenantSettings.tenant_id.in_(tenant_ids))
    result = await db.execute(stmt)
    rows = result.scalars().all()

    timezone_map = {
        tenant_id: default_timezone
        for tenant_id in tenant_ids
    }
    for row in rows:
        timezone_map[row.tenant_id] = row.timezone or default_timezone

    return timezone_map
