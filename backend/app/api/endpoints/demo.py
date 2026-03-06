"""
Demo Runner — creates demo client + appointment and runs status workflow.
Only allowed for tenant with slug="demo-service".
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.session import get_db
from app.models.models import Tenant
from app.services.demo_workflow import reset_demo, run_demo_workflow

router = APIRouter(prefix="/demo", tags=["demo"])
logger = logging.getLogger(__name__)

DEMO_SLUG = "demo-service"


async def get_demo_tenant(
    tenant_id: int = Depends(deps.get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant or tenant.slug != DEMO_SLUG:
        raise HTTPException(
            status_code=403,
            detail="Demo mode allowed only for demo tenant",
        )
    return tenant


@router.post("/run")
async def run_demo(
    tenant: Tenant = Depends(get_demo_tenant),
):
    asyncio.create_task(run_demo_workflow(tenant.id))
    return {"status": "demo_started"}


@router.post("/reset")
async def reset_demo_endpoint(
    tenant: Tenant = Depends(get_demo_tenant),
):
    return await reset_demo(tenant.id)
