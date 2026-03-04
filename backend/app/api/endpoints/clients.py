from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.db.session import get_db
from app.api import deps
from app.models.models import Client, User, UserRole
from app.core.config import settings
from pydantic import BaseModel

router = APIRouter()

class ClientOut(BaseModel):
    id: int
    telegram_id: int
    full_name: str
    phone: str
    vehicle_info: str | None = None

    class Config:
        from_attributes = True

class ClientCarInfo(BaseModel):
    full_name: str
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("/public", response_model=ClientCarInfo)
async def get_client_car_info(
    telegram_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint: returns car info for a returning client by telegram_id."""
    tenant_id = settings.PUBLIC_TENANT_ID
    if not tenant_id:
        raise HTTPException(status_code=503, detail="Service unavailable")

    stmt = select(Client).where(
        and_(Client.telegram_id == telegram_id, Client.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()

    if not client or not client.car_make:
        raise HTTPException(status_code=404, detail="Client not found or no car data")

    return client

@router.get("/", response_model=List[ClientOut])
async def read_clients(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
    current_user: User = Depends(deps.require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.STAFF]))
) -> Any:
    """
    Retrieve clients scoped by tenant.
    """
    stmt = select(Client).where(Client.tenant_id == tenant_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    clients = result.scalars().all()
    
    # Enrich ClientOut with formatted vehicle_info
    for c in clients:
        parts = []
        if c.car_make:
            parts.append(c.car_make)
        if c.car_year:
            parts.append(str(c.car_year))
        if c.vin:
            parts.append(f"({c.vin})")
        
        c.vehicle_info = " ".join(parts) if parts else None
        
    return clients
