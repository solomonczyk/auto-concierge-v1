"""
Tenant provisioning endpoint — SUPERADMIN only.
POST /api/v1/tenants  — creates tenant + admin user + default settings + (optional) service catalog.
"""
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_superadmin
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.models import Service, Tenant, TenantSettings, TenantStatus, User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter()

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


class TenantCreateRequest(BaseModel):
    name: str
    slug: str
    admin_username: str
    admin_password: str
    timezone: str = "Europe/Moscow"
    seed_services: bool = True

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not SLUG_RE.match(v):
            raise ValueError(
                "slug must be 3-50 chars, only lowercase letters, digits and hyphens, "
                "must not start or end with a hyphen"
            )
        return v

    @field_validator("admin_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("admin_password must be at least 8 characters")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("admin_username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) < 3:
            raise ValueError("admin_username must be at least 3 characters")
        return v


class TenantCreateResponse(BaseModel):
    tenant_id: int
    slug: str
    dashboard_url: str
    admin_username: str
    services_seeded: int


async def _seed_default_services(db: AsyncSession, tenant_id: int) -> int:
    """Seed a minimal set of default auto-service catalog entries for a new tenant."""
    DEFAULT_CATALOG = [
        {"name": "Замена масла и фильтра", "base_price": 800.0, "duration_minutes": 30},
        {"name": "Диагностика двигателя", "base_price": 500.0, "duration_minutes": 60},
        {"name": "Замена тормозных колодок", "base_price": 1200.0, "duration_minutes": 60},
        {"name": "Шиномонтаж (4 колеса)", "base_price": 1600.0, "duration_minutes": 60},
        {"name": "Замена воздушного фильтра", "base_price": 300.0, "duration_minutes": 15},
        {"name": "Замена свечей зажигания", "base_price": 600.0, "duration_minutes": 30},
        {"name": "Развал-схождение", "base_price": 1000.0, "duration_minutes": 60},
        {"name": "Промывка инжектора", "base_price": 1500.0, "duration_minutes": 90},
        {"name": "Замена аккумулятора", "base_price": 400.0, "duration_minutes": 30},
        {"name": "Компьютерная диагностика (OBD2)", "base_price": 500.0, "duration_minutes": 45},
    ]
    count = 0
    for item in DEFAULT_CATALOG:
        svc = Service(
            tenant_id=tenant_id,
            name=item["name"],
            base_price=item["base_price"],
            duration_minutes=item["duration_minutes"],
        )
        db.add(svc)
        count += 1
    return count


@router.post(
    "",
    response_model=TenantCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new tenant (SUPERADMIN only)",
)
async def create_tenant(
    payload: TenantCreateRequest,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TenantCreateResponse:
    # --- 1. Uniqueness checks ---
    slug_exists = await db.execute(select(Tenant).where(Tenant.slug == payload.slug))
    if slug_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with slug '{payload.slug}' already exists",
        )

    username_exists = await db.execute(select(User).where(User.username == payload.admin_username))
    if username_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.admin_username}' is already taken",
        )

    # --- 2. Create Tenant ---
    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        status=TenantStatus.ACTIVE,
    )
    db.add(tenant)
    await db.flush()  # get tenant.id before using it

    # --- 3. Create ADMIN user ---
    admin_user = User(
        tenant_id=tenant.id,
        username=payload.admin_username,
        hashed_password=get_password_hash(payload.admin_password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin_user)

    # --- 4. Create default TenantSettings ---
    tenant_settings = TenantSettings(
        tenant_id=tenant.id,
        work_start=9,
        work_end=18,
        slot_duration=30,
        timezone=payload.timezone,
    )
    db.add(tenant_settings)

    # --- 5. Seed default service catalog ---
    services_seeded = 0
    if payload.seed_services:
        services_seeded = await _seed_default_services(db, tenant.id)

    await db.commit()

    dashboard_url = f"{settings.WEBAPP_URL}/concierge/{payload.slug}"

    logger.info(
        "[Provisioning] Tenant created: id=%s slug=%s admin=%s services=%s",
        tenant.id,
        payload.slug,
        payload.admin_username,
        services_seeded,
    )

    return TenantCreateResponse(
        tenant_id=tenant.id,
        slug=payload.slug,
        dashboard_url=dashboard_url,
        admin_username=payload.admin_username,
        services_seeded=services_seeded,
    )
