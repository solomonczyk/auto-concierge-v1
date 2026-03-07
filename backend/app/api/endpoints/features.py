"""
Plan-aware feature gating and usage info.
GET /api/v1/features — feature flags for current tenant
GET /api/v1/analytics/advanced — enterprise-only (403 if not enterprise)
"""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.db.session import get_db
from app.models.models import User, Tenant
from app.services.usage_service import get_features_for_plan, can_use_feature
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

router = APIRouter()


@router.get("")
async def get_tenant_features(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Return feature flags for the current tenant's plan.
    Requires authentication.
    """
    tenant_id = current_user.tenant_id
    if not tenant_id:
        return get_features_for_plan(None)

    stmt = select(Tenant).options(joinedload(Tenant.tariff_plan)).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    plan_name = tenant.tariff_plan.name if (tenant and tenant.tariff_plan) else None
    return get_features_for_plan(plan_name)


@router.get("/analytics/advanced")
async def get_advanced_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Enterprise-only: advanced analytics stub.
    Returns 403 if tenant plan is not enterprise.
    """
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "feature_restricted", "feature": "advanced_analytics", "required_plan": "enterprise"},
        )

    stmt = select(Tenant).options(joinedload(Tenant.tariff_plan)).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    plan_name = tenant.tariff_plan.name if (tenant and tenant.tariff_plan) else None

    if not can_use_feature(plan_name, "advanced_analytics"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "feature_restricted",
                "feature": "advanced_analytics",
                "required_plan": "enterprise",
                "current_plan": plan_name or "starter",
            },
        )

    # Stub response — real analytics would go here
    return {"message": "Advanced analytics (enterprise)", "data": []}
