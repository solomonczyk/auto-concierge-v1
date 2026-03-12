"""
Admin Control Plane — unified SUPERADMIN API.
/api/v1/admin/control-plane/summary
/api/v1/admin/tenants/overview
/api/v1/admin/tenants/{tenant_id}
/api/v1/admin/tenants/{tenant_id}/activate-bot
/api/v1/admin/tenants/{tenant_id}/provision-webhook
/api/v1/admin/tenants/{tenant_id}/finalize-onboarding

All endpoints: SUPERADMIN only. Reuses existing services (readiness, onboarding, webhook).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_superadmin
from app.db.session import get_db
from app.models.models import Service, Shop, Tenant, TenantStatus, User
from app.models.telegram_bot import TelegramBot
from app.schemas.admin_control_plane import (
    ActivateBotResponse,
    ControlPlaneSummaryResponse,
    FinalizeOnboardingResponse,
    ProvisionWebhookResponse,
    ShopInfo,
    TelegramBotInfo,
    TenantDetailResponse,
    TenantOnboardingState,
    TenantOverviewItem,
    TenantReadinessFlags,
)
from app.services.control_plane_summary_service import compute_platform_summary
from app.services.onboarding_service import finalize_tenant_onboarding
from app.services.tenant_readiness_service import (
    compute_onboarding_state,
    compute_tenant_readiness,
    get_webhook_operational_state,
)
from app.services.telegram_webhook_service import provision_telegram_webhook

router = APIRouter(prefix="/admin", tags=["admin", "control-plane"])


@router.get(
    "/control-plane/summary",
    response_model=ControlPlaneSummaryResponse,
    summary="Platform-wide control plane summary (SUPERADMIN only)",
)
async def get_control_plane_summary(
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> ControlPlaneSummaryResponse:
    data = await compute_platform_summary(db)
    return ControlPlaneSummaryResponse(**data)


@router.get(
    "/tenants/overview",
    response_model=list[TenantOverviewItem],
    summary="List all tenants with readiness (SUPERADMIN only)",
)
async def get_tenants_overview(
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> list[TenantOverviewItem]:
    result = await db.execute(select(Tenant).order_by(Tenant.id))
    tenants = result.scalars().all()
    items = []
    for tenant in tenants:
        flags = await compute_tenant_readiness(db, tenant.id)
        items.append(
            TenantOverviewItem(
                tenant_id=tenant.id,
                name=tenant.name or "",
                slug=tenant.slug,
                status=tenant.status.value,
                shop_configured=flags.get("shop_configured", False),
                services_configured=flags.get("services_configured", False),
                telegram_bot_registered=flags.get("telegram_bot_registered", False),
                telegram_webhook_active=flags.get("telegram_webhook_active", False),
                booking_ready=flags.get("booking_ready", False),
            )
        )
    return items


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantDetailResponse,
    summary="Tenant detail (SUPERADMIN only)",
)
async def get_tenant_detail(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TenantDetailResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    onboarding_state = await compute_onboarding_state(db, tenant_id)
    flags = await compute_tenant_readiness(db, tenant_id)
    webhook_state = await get_webhook_operational_state(db, tenant_id)

    shop = (await db.execute(select(Shop).where(Shop.tenant_id == tenant_id).limit(1))).scalar_one_or_none()
    shop_info = ShopInfo(id=shop.id, name=shop.name, address=shop.address) if shop else None

    svc_count = (
        await db.execute(select(func.count()).select_from(Service).where(Service.tenant_id == tenant_id))
    ).scalar_one()

    bot = (
        await db.execute(
            select(TelegramBot).where(
                TelegramBot.tenant_id == tenant_id,
                TelegramBot.is_active.is_(True),
            ).limit(1)
        )
    ).scalar_one_or_none()
    bot_info = None
    if bot:
        status_val = webhook_state.get("webhook_status")
        bot_info = TelegramBotInfo(
            id=bot.id,
            bot_username=bot.bot_username,
            is_active=bool(bot.is_active),
            webhook_status=str(status_val) if status_val else "not_configured",
            webhook_last_error=webhook_state.get("webhook_last_error"),
            webhook_last_synced_at=webhook_state.get("webhook_last_synced_at"),
        )

    return TenantDetailResponse(
        tenant_id=tenant.id,
        name=tenant.name or "",
        slug=tenant.slug,
        status=tenant.status.value,
        onboarding_state=TenantOnboardingState(
            tenant_created=onboarding_state.get("tenant_created", False),
            tariff_assigned=onboarding_state.get("tariff_assigned", False),
            telegram_bot_registered=onboarding_state.get("telegram_bot_registered", False),
            webhook_provisioned=onboarding_state.get("webhook_provisioned", False),
            readiness_ok=onboarding_state.get("readiness_ok", False),
            onboarding_complete=onboarding_state.get("onboarding_complete", False),
            missing_steps=onboarding_state.get("missing_steps", []),
        ),
        readiness=TenantReadinessFlags(**flags),
        shop=shop_info,
        services_count=svc_count,
        telegram_bot=bot_info,
        created_at=tenant.created_at.isoformat() if tenant.created_at else None,
    )


@router.post(
    "/tenants/{tenant_id}/activate-bot",
    response_model=ActivateBotResponse,
    summary="Validate tenant ready for bot activation (SUPERADMIN only)",
)
async def post_activate_bot(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> ActivateBotResponse:
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
    if not bot.webhook_secret or not str(bot.webhook_secret).strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bot has no webhook secret; run provision webhook first",
        )

    return ActivateBotResponse(
        tenant_id=tenant_id,
        action="activate_bot",
        success=True,
        message="Telegram bot is ready for activation",
    )


@router.post(
    "/tenants/{tenant_id}/provision-webhook",
    response_model=ProvisionWebhookResponse,
    summary="Provision Telegram webhook for tenant (SUPERADMIN only)",
)
async def post_provision_webhook(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> ProvisionWebhookResponse:
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
    if not bot.webhook_secret or not str(bot.webhook_secret).strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bot has no webhook secret; run activate webhook first",
        )
    if not bot.bot_username or not str(bot.bot_username).strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bot has no username; required for webhook URL",
        )

    result = await provision_telegram_webhook(db, bot)

    return ProvisionWebhookResponse(
        tenant_id=tenant_id,
        action="provision_webhook",
        success=result.success,
        status=result.status,
        message=result.message,
        error=result.error,
    )


@router.post(
    "/tenants/{tenant_id}/finalize-onboarding",
    response_model=FinalizeOnboardingResponse,
    summary="Finalize tenant onboarding (SUPERADMIN only)",
)
async def post_finalize_onboarding(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> FinalizeOnboardingResponse:
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    ok, message = await finalize_tenant_onboarding(db, tenant_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return FinalizeOnboardingResponse(
        tenant_id=tenant_id,
        action="finalize_onboarding",
        finalized=True,
        message=message,
    )
