from fastapi import HTTPException, Path, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.models import Tenant
from app.core.context import tenant_id_context


async def get_tenant_id_by_slug(
    slug: str = Path(...),
    db: AsyncSession = Depends(get_db),
) -> int:
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail=f"Автосервис '{slug}' не найден")
    tenant_id_context.set(tenant.id)
    return tenant.id
