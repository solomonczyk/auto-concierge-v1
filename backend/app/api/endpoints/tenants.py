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
from app.models.models import Service, Shop, TariffPlan, Tenant, TenantSettings, TenantStatus, User, UserRole
from app.schemas.tenant_lifecycle import TenantLifecycleResponse, TenantStatusRead, TenantStatusUpdate
from app.schemas.tenant_provisioning import (
    TenantOnboardingStateResponse,
    TenantTariffAssignRequest,
    TenantTariffAssignResponse,
)
from app.models.telegram_bot import TelegramBot
from app.services.billing_gate import check_billing_ok
from app.services.onboarding_service import finalize_tenant_onboarding
from app.services.tenant_readiness_service import (
    compute_onboarding_state,
    compute_tenant_readiness,
    get_webhook_operational_state,
)
from app.services.telegram_webhook_service import provision_telegram_webhook

logger = logging.getLogger(__name__)

router = APIRouter()

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


class TenantCreateRequest(BaseModel):
    """Full provisioning: name, slug, admin; optional contact_email, timezone, seed_services."""

    name: str
    slug: str
    admin_username: str
    admin_password: str
    contact_email: str | None = None
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
    """Minimal contract: id, name, slug, status; extended with shop/admin when full provisioning."""

    id: int
    name: str
    slug: str
    status: str
    tenant_id: int | None = None  # alias, same as id
    shop_id: int | None = None
    dashboard_url: str | None = None
    admin_username: str | None = None
    services_seeded: int = 0
    onboarding_status: str = "pending"
    is_ready_for_booking: bool = False


class TenantReadinessFlags(BaseModel):
    """Base schema for readiness flags — single source of truth."""

    shop_configured: bool
    services_configured: bool
    telegram_bot_registered: bool
    telegram_webhook_active: bool
    booking_ready: bool
    tenant_status: str
    tenant_operational: bool


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
    # --- 1. Uniqueness / idempotency: duplicate slug → 409 (retry-safe: no duplicate tenant) ---
    slug_exists = await db.execute(select(Tenant).where(Tenant.slug == payload.slug))
    existing = slug_exists.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with slug '{payload.slug}' already exists (id={existing.id}). Use a different slug or update the existing tenant.",
        )

    username_exists = await db.execute(select(User).where(User.username == payload.admin_username))
    if username_exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.admin_username}' is already taken",
        )

    # --- 2. Create Tenant (SaaS: start PENDING; finalize to ACTIVE after onboarding) ---
    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        status=TenantStatus.PENDING,
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
    flags = await compute_tenant_readiness(db, tenant.id)
    readiness_ok = flags.get("booking_ready", False)

    logger.info(
        "[Provisioning] Tenant created: id=%s slug=%s shop_id=%s admin=%s services=%s status=%s",
        tenant.id,
        payload.slug,
        shop.id,
        payload.admin_username,
        services_seeded,
        tenant.status.value,
    )

    return TenantCreateResponse(
        id=tenant.id,
        name=tenant.name,
        slug=payload.slug,
        status=tenant.status.value,
        tenant_id=tenant.id,
        shop_id=shop.id,
        dashboard_url=dashboard_url,
        admin_username=payload.admin_username,
        services_seeded=services_seeded,
        onboarding_status="ready" if readiness_ok else "pending",
        is_ready_for_booking=readiness_ok,
    )


@router.post(
    "/{tenant_id}/tariff",
    response_model=TenantTariffAssignResponse,
    summary="Assign tariff to tenant (SUPERADMIN only)",
)
async def assign_tenant_tariff(
    tenant_id: int,
    payload: TenantTariffAssignRequest,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TenantTariffAssignResponse:
    if not payload.tariff_plan_id and not payload.tariff_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either tariff_plan_id or tariff_code",
        )
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if payload.tariff_plan_id:
        plan = (await db.execute(select(TariffPlan).where(TariffPlan.id == payload.tariff_plan_id))).scalar_one_or_none()
    else:
        plan = (
            await db.execute(
                select(TariffPlan).where(TariffPlan.name == (payload.tariff_code or "").strip().lower())
            )
        ).scalar_one_or_none()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tariff plan not found: {payload.tariff_plan_id or payload.tariff_code}",
        )
    tenant.tariff_plan_id = plan.id
    await db.commit()
    await db.refresh(tenant)
    return TenantTariffAssignResponse(
        tenant_id=tenant.id,
        tariff_plan_id=plan.id,
        tariff_code=plan.name,
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


@router.patch(
    "/{tenant_id}/status",
    response_model=TenantStatusRead,
    summary="Update tenant lifecycle status (SUPERADMIN only)",
)
async def update_tenant_status(
    tenant_id: int,
    payload: TenantStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TenantStatusRead:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    tenant.status = payload.status
    await db.commit()
    await db.refresh(tenant)
    return TenantStatusRead(tenant_id=tenant.id, status=tenant.status.value)


@router.get(
    "/{tenant_id}/lifecycle",
    response_model=TenantLifecycleResponse,
    summary="Get tenant lifecycle summary (SUPERADMIN only)",
)
async def get_tenant_lifecycle(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TenantLifecycleResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    flags = await compute_tenant_readiness(db, tenant_id)
    operational = flags.get("tenant_operational", False)
    billing_ok = await check_billing_ok(db, tenant_id)
    readiness_ok = flags.get("booking_ready", False) and operational
    return TenantLifecycleResponse(
        tenant_id=tenant.id,
        status=tenant.status.value,
        operational=operational,
        billing_ok=billing_ok,
        readiness_ok=readiness_ok,
    )


@router.get(
    "/{tenant_id}/onboarding",
    response_model=TenantOnboardingStateResponse,
    summary="Get tenant onboarding state (SUPERADMIN only)",
)
async def get_tenant_onboarding(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TenantOnboardingStateResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    state = await compute_onboarding_state(db, tenant_id)
    return TenantOnboardingStateResponse(tenant_id=tenant_id, **state)


@router.post(
    "/{tenant_id}/onboarding/finalize",
    summary="Finalize onboarding: set tenant to ACTIVE when complete (SUPERADMIN only)",
)
async def post_tenant_onboarding_finalize(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
):
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    ok, message = await finalize_tenant_onboarding(db, tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"tenant_id": tenant_id, "finalized": True, "message": message}


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
