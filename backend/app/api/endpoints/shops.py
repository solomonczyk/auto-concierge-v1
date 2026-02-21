from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from sqlalchemy.orm import joinedload
from app.db.session import get_db
from app.models.models import Shop, User, UserRole, Tenant, TariffPlan
from app.api import deps
from pydantic import BaseModel

router = APIRouter()

class ShopCreate(BaseModel):
    name: str
    address: str

class ShopRead(ShopCreate):
    id: int
    class Config:
        from_attributes = True

@router.post("/", response_model=ShopRead)
async def create_shop(
    shop: ShopCreate, 
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
    current_user: User = Depends(deps.require_role([UserRole.ADMIN]))
):
    # Check shop limit
    stmt_count = select(func.count(Shop.id)).where(Shop.tenant_id == tenant_id)
    current_count = (await db.execute(stmt_count)).scalar() or 0
    
    stmt_tenant = select(Tenant).options(joinedload(Tenant.tariff_plan)).where(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt_tenant)).scalar_one()
    
    max_shops = tenant.tariff_plan.max_shops if tenant.tariff_plan else 1
    if current_count >= max_shops:
        raise HTTPException(
            status_code=403,
            detail=f"Shop limit reached ({max_shops}). Please upgrade your plan."
        )

    db_shop = Shop(tenant_id=tenant_id, name=shop.name, address=shop.address)
    db.add(db_shop)
    await db.commit()
    await db.refresh(db_shop)
    return db_shop

@router.get("/", response_model=List[ShopRead])
async def read_shops(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id)
):
    result = await db.execute(select(Shop).where(Shop.tenant_id == tenant_id).offset(skip).limit(limit))
    shops = result.scalars().all()
    return shops

@router.get("/stats")
async def get_shop_stats(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
    current_user: User = Depends(deps.require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    from app.services.analytics_service import analytics_service
    return await analytics_service.get_tenant_stats(db, tenant_id)
