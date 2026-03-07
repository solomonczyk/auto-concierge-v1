from datetime import date, datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.core.slots import get_available_slots
from app.api.deps import get_current_tenant_id
from app.models.models import Shop

router = APIRouter()


@router.get("/available", response_model=List[datetime])
async def get_slots(
    shop_id: int,
    service_duration: int,
    target_date: date = Query(..., description="Date to check for slots (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
):
    stmt = select(Shop).where(Shop.id == shop_id, Shop.tenant_id == tenant_id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Shop not found")
    return await get_available_slots(shop_id, service_duration, target_date, db)


@router.get("/public", response_model=List[datetime])
async def get_public_slots():
    """Deprecated: use /{slug}/slots/public instead."""
    raise HTTPException(
        status_code=410,
        detail="Этот endpoint устарел. Используйте /api/v1/{slug}/slots/public",
    )
