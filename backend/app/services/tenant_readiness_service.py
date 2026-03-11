"""
Tenant readiness calculation — single source of truth for readiness/control-plane.
Contract: shop_configured, services_configured, telegram_bot_registered,
telegram_webhook_active, booking_ready.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import exists

from app.models.models import Service, Shop
from app.models.telegram_bot import TelegramBot


async def compute_tenant_readiness(db: AsyncSession, tenant_id: int) -> dict:
    """
    Compute readiness flags for a tenant.
    Returns dict: shop_configured, services_configured, telegram_bot_registered,
    telegram_webhook_active, booking_ready.
    """
    shop = (await db.execute(select(Shop).where(Shop.tenant_id == tenant_id).limit(1))).scalar_one_or_none()
    service = (await db.execute(select(Service).where(Service.tenant_id == tenant_id).limit(1))).scalar_one_or_none()

    # telegram_bot_registered: at least one active bot for tenant
    bot_exists = (
        await db.execute(
            select(
                exists().where(
                    TelegramBot.tenant_id == tenant_id,
                    TelegramBot.is_active.is_(True),
                )
            )
        )
    ).scalar()
    telegram_bot_registered = bool(bot_exists)

    # telegram_webhook_active: at least one active bot with non-empty webhook_secret (multi-bot safe)
    bots_with_secret = (
        await db.execute(
            select(TelegramBot)
            .where(
                TelegramBot.tenant_id == tenant_id,
                TelegramBot.is_active.is_(True),
                TelegramBot.webhook_secret.isnot(None),
            )
        )
    ).scalars().all()
    telegram_webhook_active = any(
        b.webhook_secret and b.webhook_secret.strip() for b in bots_with_secret
    )

    shop_configured = shop is not None
    services_configured = service is not None
    booking_ready = shop_configured and services_configured and telegram_bot_registered and telegram_webhook_active

    return {
        "shop_configured": shop_configured,
        "services_configured": services_configured,
        "telegram_bot_registered": telegram_bot_registered,
        "telegram_webhook_active": telegram_webhook_active,
        "booking_ready": booking_ready,
    }
