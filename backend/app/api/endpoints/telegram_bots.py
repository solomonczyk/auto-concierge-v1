"""
Telegram bot registration — SaaS channel binding.
POST /api/v1/tenants/{tenant_id}/telegram-bots — register bot for tenant (SUPERADMIN only).
POST /api/v1/tenants/{tenant_id}/telegram-bots/{telegram_bot_id}/activate — activate webhook (SUPERADMIN only).
"""
import logging
import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_superadmin
from app.core.config import settings
from app.db.session import get_db
from app.models.models import Tenant, User
from app.models.telegram_bot import TelegramBot
from app.services.telegram_webhook_service import provision_telegram_webhook

logger = logging.getLogger(__name__)

router = APIRouter()


class TelegramBotRegisterRequest(BaseModel):
    """Request schema for registering a Telegram bot for a tenant (SaaS onboarding)."""

    bot_token: str
    bot_username: Optional[str] = None
    display_name: Optional[str] = None  # optional human-readable label
    is_active: bool = True

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("bot_token must not be empty")
        return v


class TelegramBotRegisterResponse(BaseModel):
    """Response schema for bot registration — tenant_id, bot_username, is_active, webhook info."""

    telegram_bot_id: int
    tenant_id: int
    bot_username: Optional[str]
    is_active: bool
    webhook_url: Optional[str]
    webhook_secret_required: bool
    onboarding_status: str


class TelegramBotActivateResponse(BaseModel):
    telegram_bot_id: int
    tenant_id: int
    webhook_url: str
    activation_status: str
    onboarding_status: str


class WebhookProvisionResponse(BaseModel):
    """Response for POST .../bots/{bot_id}/webhook — SaaS onboarding."""

    tenant_id: int
    bot_id: int
    bot_username: str | None
    webhook_url: str
    webhook_secret_present: bool


@router.post(
    "/{tenant_id}/bots",
    response_model=TelegramBotRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Telegram bot for tenant (SUPERADMIN only) — SaaS onboarding",
)
@router.post(
    "/{tenant_id}/telegram-bots",
    response_model=TelegramBotRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Telegram bot for tenant (SUPERADMIN only) — legacy path",
)
async def register_telegram_bot(
    tenant_id: int,
    payload: TelegramBotRegisterRequest,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TelegramBotRegisterResponse:
    # 1. Tenant must exist
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # 2. bot_token must not be used by another tenant
    existing = (
        await db.execute(
            select(TelegramBot).where(
                TelegramBot.bot_token == payload.bot_token,
                TelegramBot.tenant_id != tenant_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This bot token is already registered to another tenant",
        )

    # 3. Upsert: create or update single bot for this tenant (retry-safe: no duplicate; re-register updates token)
    existing_bot_same_tenant = (
        await db.execute(select(TelegramBot).where(TelegramBot.tenant_id == tenant_id))
    ).scalars().first()
    if existing_bot_same_tenant:
        # Update existing bot for this tenant; do not create duplicate
        bot = existing_bot_same_tenant
        bot.bot_token = payload.bot_token
        bot.bot_username = payload.bot_username or bot.bot_username
        bot.is_active = payload.is_active
    else:
        bot = TelegramBot(
            tenant_id=tenant_id,
            bot_token=payload.bot_token,
            bot_username=payload.bot_username,
            is_active=payload.is_active,
        )
        db.add(bot)

    await db.commit()
    await db.refresh(bot)

    logger.info(
        "[TelegramBot] Registered: id=%s tenant_id=%s username=%s",
        bot.id,
        tenant_id,
        payload.bot_username,
    )

    if bot.bot_username:
        base = (settings.SITE_URL or "").rstrip("/")
        webhook_path = f"{settings.API_V1_STR}/webhook/{bot.bot_username}"
        webhook_url = f"{base}{webhook_path}" if base else webhook_path
        onboarding_status = "pending_webhook"
    else:
        webhook_url = None
        onboarding_status = "bot_registered"

    return TelegramBotRegisterResponse(
        telegram_bot_id=bot.id,
        tenant_id=tenant_id,
        bot_username=bot.bot_username,
        is_active=bot.is_active,
        webhook_url=webhook_url,
        webhook_secret_required=True,
        onboarding_status=onboarding_status,
    )


@router.post(
    "/{tenant_id}/bots/{bot_id}/webhook",
    response_model=WebhookProvisionResponse,
    summary="Provision webhook for tenant bot (SUPERADMIN only) — SaaS onboarding",
)
async def provision_bot_webhook(
    tenant_id: int,
    bot_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> WebhookProvisionResponse:
    bot = (
        await db.execute(
            select(TelegramBot).where(
                TelegramBot.id == bot_id,
                TelegramBot.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telegram bot not found")
    if not bot.bot_username or not bot.bot_username.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bot_username is required for webhook; re-register the bot with username",
        )
    if not bot.webhook_secret or not bot.webhook_secret.strip():
        bot.webhook_secret = secrets.token_urlsafe(32)[:256]
        await db.commit()
        await db.refresh(bot)
    # Retry-safe: repeated call updates secret and re-calls Telegram setWebhook
    await provision_telegram_webhook(db, bot)
    base = (settings.SITE_URL or "").rstrip("/")
    webhook_path = f"{settings.API_V1_STR}/webhook/{bot.bot_username.strip()}"
    webhook_url = f"{base}{webhook_path}" if base else webhook_path
    return WebhookProvisionResponse(
        tenant_id=tenant_id,
        bot_id=bot.id,
        bot_username=bot.bot_username,
        webhook_url=webhook_url,
        webhook_secret_present=bool(bot.webhook_secret and bot.webhook_secret.strip()),
    )


@router.post(
    "/{tenant_id}/telegram-bots/{telegram_bot_id}/activate",
    response_model=TelegramBotActivateResponse,
    summary="Activate webhook for Telegram bot (SUPERADMIN only)",
)
async def activate_telegram_bot(
    tenant_id: int,
    telegram_bot_id: int,
    db: AsyncSession = Depends(get_db),
    _superadmin: User = Depends(require_superadmin),
) -> TelegramBotActivateResponse:
    # 1. Bot must exist and belong to tenant
    bot = (
        await db.execute(
            select(TelegramBot).where(
                TelegramBot.id == telegram_bot_id,
                TelegramBot.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telegram bot not found")

    # 2. bot_username required for webhook route
    if not bot.bot_username or not bot.bot_username.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bot_username is required for webhook activation. Re-register the bot with bot_username.",
        )

    # 3. Build webhook_url
    base = (settings.SITE_URL or "").rstrip("/")
    webhook_path = f"{settings.API_V1_STR}/webhook/{bot.bot_username.strip()}"
    webhook_url = f"{base}{webhook_path}" if base else webhook_path

    # 4. Generate and save per-bot webhook secret (tenant/bot isolation)
    webhook_secret = secrets.token_urlsafe(32)[:256]
    bot.webhook_secret = webhook_secret
    await db.commit()
    await db.refresh(bot)

    # 5. Call Telegram setWebhook with bot-level secret
    api_url = f"https://api.telegram.org/bot{bot.bot_token}/setWebhook"
    payload = {"url": webhook_url, "secret_token": bot.webhook_secret}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(api_url, json=payload)
    except Exception as e:
        logger.exception("[TelegramBot] setWebhook failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to reach Telegram API",
        ) from e

    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if not data.get("ok"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=data.get("description", "Telegram setWebhook failed"),
        )

    logger.info(
        "[TelegramBot] Activated: id=%s tenant_id=%s webhook=%s",
        telegram_bot_id,
        tenant_id,
        webhook_url,
    )

    return TelegramBotActivateResponse(
        telegram_bot_id=telegram_bot_id,
        tenant_id=tenant_id,
        webhook_url=webhook_url,
        activation_status="activated",
        onboarding_status="ready",
    )
