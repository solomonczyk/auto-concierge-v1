from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
    return clients
