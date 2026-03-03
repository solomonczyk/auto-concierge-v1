from datetime import date, datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.slots import get_available_slots
from app.core.config import settings
from app.models.models import Tenant
from app.bot.tenant import get_tenant_shop

router = APIRouter()

@router.get("/available", response_model=List[datetime])
async def get_slots(
    shop_id: int,
    service_duration: int,
    target_date: date = Query(..., description="Date to check for slots (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a list of available start times for a given shop and duration on a specific date.
    """
    return await get_available_slots(shop_id, service_duration, target_date, db)

@router.get("/public", response_model=List[datetime])
async def get_public_slots(
    service_duration: int,
    target_date: date = Query(..., description="Date to check for slots (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db)
):
    if not settings.PUBLIC_TENANT_ID:
        raise HTTPException(status_code=503, detail="Публичный доступ к слотам временно недоступен")

    tenant_stmt = select(Tenant).where(Tenant.id == settings.PUBLIC_TENANT_ID)
    tenant = (await db.execute(tenant_stmt)).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Публичный профиль сервиса не найден")

    shop = await get_tenant_shop(db, tenant)
    if not shop:
        raise HTTPException(status_code=400, detail="Сервис временно недоступен")

    return await get_available_slots(shop.id, service_duration, target_date, db)
