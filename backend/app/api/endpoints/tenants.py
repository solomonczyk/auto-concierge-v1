"""
Tenant provisioning endpoint — SUPERADMIN only.
POST /api/v1/tenants — creates tenant + default shop + admin user + default settings + (optional) service catalog.
GET /api/v1/tenants/control-plane — list all tenants with readiness (SUPERADMIN).
GET /api/v1/tenants/{tenant_id}/control-plane — tenant control-plane detail (SUPERADMIN).
GET /api/v1/tenants/{tenant_id}/readiness — tenant readiness status (SUPERADMIN).
POST /api/v1/tenants/{tenant_id}/control-plane/activate-bot — validate tenant ready for bot activation (SUPERADMIN).
POST /api/v1/tenants/{tenant_id}/control-plane/provision-webhook — provision Telegram webhook via API (SUPERADMIN).
"""
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_superadmin
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.models import Service, Shop, Tenant, TenantSettings, TenantStatus, User, UserRole
from app.models.telegram_bot import TelegramBot
from app.services.tenant_readiness_service import compute_tenant_readiness, get_webhook_operational_state
from app.services.telegram_webhook_service import provision_telegram_webhook

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
    shop_id: int
    dashboard_url: str
    admin_username: str
    services_seeded: int
    onboarding_status: str
    is_ready_for_booking: bool


class TenantReadinessFlags(BaseModel):
    """Base schema for readiness flags — single source of truth."""

    shop_configured: bool
    services_configured: bool
    telegram_bot_registered: bool
    telegram_webhook_active: bool
    booking_ready: bool


class TenantReadinessResponse(TenantReadinessFlags):
    """Readiness endpoint — tenant_id + flags."""

    tenant_id: int


class TenantControlPlaneItem(TenantReadinessFlags):
    """Control-plane list/detail — tenant_id, name, is_active + flags + webhook operational state."""

    tenant_id: int
    name: str
    is_active: bool
    webhook_status: str | None = None
    webhook_last_error: str | None = None
    webhook_last_synced_at: str | None = None


class ActivateBotControlPlaneResponse(BaseModel):
    """Control-plane action result for activate-bot."""

    tenant_id: int
    action: str = "activate_bot"
    success: bool = True
    message: str = "Telegram bot is ready for activation"


class ProvisionWebhookControlPlaneResponse(BaseModel):
    """Control-plane action result for provision-webhook."""

    tenant_id: int
    action: str = "provision_webhook"
    success: bool
    status: str
    message: str
    error: str | None = None


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

    # --- 3. Create default Shop (same transaction, required for get_tenant_shop / public booking) ---
    default_shop_name = (payload.name or payload.slug).strip()[:100]
    shop = Shop(
        tenant_id=tenant.id,
        name=default_shop_name or payload.slug,
        address=None,
    )
    db.add(shop)
    await db.flush()  # get shop.id for response

    # --- 4. Create ADMIN user ---
    admin_user = User(
        tenant_id=tenant.id,
        username=payload.admin_username,
        hashed_password=get_password_hash(payload.admin_password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin_user)

    # --- 5. Create default TenantSettings ---
    tenant_settings = TenantSettings(
        tenant_id=tenant.id,
        work_start=9,
        work_end=18,
        slot_duration=30,
        timezone=payload.timezone,
    )
    db.add(tenant_settings)

    # --- 6. Seed default service catalog ---
    services_seeded = 0
    if payload.seed_services:
        services_seeded = await _seed_default_services(db, tenant.id)

    await db.commit()

    dashboard_url = f"{settings.SITE_URL}/concierge/{payload.slug}"

    logger.info(
        "[Provisioning] Tenant created: id=%s slug=%s shop_id=%s admin=%s services=%s",
        tenant.id,
        payload.slug,
        shop.id,
        payload.admin_username,
        services_seeded,
    )

    return TenantCreateResponse(
        tenant_id=tenant.id,
        slug=payload.slug,
        shop_id=shop.id,
        dashboard_url=dashboard_url,
        admin_username=payload.admin_username,
        services_seeded=services_seeded,
        onboarding_status="ready",
        is_ready_for_booking=True,
    )


@router.get(
    "/control-plane",
    response_model=list[TenantControlPlaneItem],
    summary="List all tenants with readiness (SUPERADMIN only)",
)
async def get_tenants_control_plane(
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> list[TenantControlPlaneItem]:
    result = await db.execute(select(Tenant).order_by(Tenant.id))
    tenants = result.scalars().all()
    items = []
    for tenant in tenants:
        # TODO: N+1 — list endpoint does one compute_tenant_readiness per tenant.
        flags = await compute_tenant_readiness(db, tenant.id)
        webhook_state = await get_webhook_operational_state(db, tenant.id)
        items.append(
            TenantControlPlaneItem(
                tenant_id=tenant.id,
                name=tenant.name or "",
                is_active=tenant.status == TenantStatus.ACTIVE,
                **flags,
                **webhook_state,
            )
        )
    return items


@router.get(
    "/{tenant_id}/control-plane",
    response_model=TenantControlPlaneItem,
    summary="Get tenant control-plane detail (SUPERADMIN only)",
)
async def get_tenant_control_plane_detail(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TenantControlPlaneItem:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    flags = await compute_tenant_readiness(db, tenant_id)
    webhook_state = await get_webhook_operational_state(db, tenant_id)
    return TenantControlPlaneItem(
        tenant_id=tenant.id,
        name=tenant.name or "",
        is_active=tenant.status == TenantStatus.ACTIVE,
        **flags,
        **webhook_state,
    )


@router.get(
    "/{tenant_id}/readiness",
    response_model=TenantReadinessResponse,
    summary="Get tenant readiness status (SUPERADMIN only)",
)
async def get_tenant_readiness(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TenantReadinessResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    flags = await compute_tenant_readiness(db, tenant_id)
    return TenantReadinessResponse(tenant_id=tenant_id, **flags)


@router.post(
    "/{tenant_id}/control-plane/activate-bot",
    response_model=ActivateBotControlPlaneResponse,
    summary="Control-plane: validate tenant ready for bot activation (SUPERADMIN only)",
)
async def activate_bot_control_plane(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> ActivateBotControlPlaneResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    bot = (
        await db.execute(
            select(TelegramBot).where(
                TelegramBot.tenant_id == tenant_id,
                TelegramBot.is_active.is_(True),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active Telegram bot for tenant",
        )
    if not bot.webhook_secret or not bot.webhook_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bot has no webhook secret; run activate webhook first",
        )

    return ActivateBotControlPlaneResponse(
        tenant_id=tenant_id,
        action="activate_bot",
        success=True,
        message="Telegram bot is ready for activation",
    )


@router.post(
    "/{tenant_id}/control-plane/provision-webhook",
    response_model=ProvisionWebhookControlPlaneResponse,
    summary="Control-plane: provision Telegram webhook via API (SUPERADMIN only)",
)
async def provision_webhook_control_plane(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> ProvisionWebhookControlPlaneResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    bot = (
        await db.execute(
            select(TelegramBot).where(
                TelegramBot.tenant_id == tenant_id,
                TelegramBot.is_active.is_(True),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active Telegram bot for tenant",
        )
    if not bot.webhook_secret or not bot.webhook_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bot has no webhook secret; run activate webhook first",
        )
    if not bot.bot_username or not bot.bot_username.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bot has no username; required for webhook URL",
        )

    result = await provision_telegram_webhook(db, bot)

    return ProvisionWebhookControlPlaneResponse(
        tenant_id=tenant_id,
        action="provision_webhook",
        success=result.success,
        status=result.status,
        message=result.message,
        error=result.error,
    )
