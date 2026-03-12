from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.api import deps
from app.models.models import Client, User, UserRole
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
async def get_client_car_info():
    """Deprecated: use /{slug}/clients/public instead."""
    raise HTTPException(
        status_code=410,
        detail="Этот endpoint устарел. Используйте /api/v1/{slug}/clients/public",
    )


@router.get("/", response_model=List[ClientOut])
async def read_clients(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
    current_user: User = Depends(deps.require_role([UserRole.ADMIN, UserRole.MANAGER, UserRole.STAFF])),
) -> Any:
    """
    Retrieve clients scoped by tenant. Excludes soft-deleted.
    vehicle_info is built from ClientAutoProfile (auto-service extension).
    """
    _client_not_deleted = Client.deleted_at.is_(None)
    stmt = (
        select(Client)
        .where(and_(Client.tenant_id == tenant_id, _client_not_deleted))
        .options(selectinload(Client.auto_profile))
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    clients = result.scalars().all()

    for c in clients:
        parts = []
        profile = c.auto_profile
        if profile:
            if profile.car_make:
                parts.append(profile.car_make)
            if profile.car_year is not None:
                parts.append(str(profile.car_year))
            if profile.vin:
                parts.append(f"({profile.vin})")
        c.vehicle_info = " ".join(parts) if parts else None

    return clients
