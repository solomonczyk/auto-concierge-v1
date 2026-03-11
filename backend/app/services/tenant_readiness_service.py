"""
Tenant readiness calculation — single source of truth for readiness/control-plane.

Readiness vs provisioning semantics (normalized):
- telegram_webhook_active (readiness): tenant is ready for webhook provisioning.
  True when: at least one active bot with non-empty webhook_secret.
  Meaning: tenant has the prerequisites; provision-webhook can be called.
- webhook_status=active (TelegramBot.provisioning): Telegram webhook is actually provisioned.
  True when: setWebhook API succeeded; bot.webhook_status == "active".
  Meaning: Telegram API has the webhook URL; real operational state.

Webhook operational state: webhook_status, webhook_last_error, webhook_last_synced_at.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import exists

from app.models.models import Service, Shop, Tenant
from app.models.telegram_bot import TelegramBot, WebhookProvisioningStatus
from app.services.tenant_lifecycle_guard import check_tenant_operational_status


async def compute_tenant_readiness(db: AsyncSession, tenant_id: int) -> dict:
    """
    Compute readiness flags for a tenant.
    Returns dict: shop_configured, services_configured, telegram_bot_registered,
    telegram_webhook_active, booking_ready, tenant_status, tenant_operational.
    """
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    tenant_status = tenant.status.value if tenant else "unknown"
    tenant_operational = False
    if tenant:
        operational, _ = await check_tenant_operational_status(db, tenant_id)
        tenant_operational = operational

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
        "tenant_status": tenant_status,
        "tenant_operational": tenant_operational,
    }


async def get_webhook_operational_state(db: AsyncSession, tenant_id: int) -> dict:
    """
    Get webhook provisioning operational state from active bot.
    Returns: webhook_status, webhook_last_error, webhook_last_synced_at (ISO string or None).
    """
    bot = (
        await db.execute(
            select(TelegramBot)
            .where(
                TelegramBot.tenant_id == tenant_id,
                TelegramBot.is_active.is_(True),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if not bot:
        return {
            "webhook_status": WebhookProvisioningStatus.NOT_CONFIGURED,
            "webhook_last_error": None,
            "webhook_last_synced_at": None,
        }
    return {
        "webhook_status": bot.webhook_status or WebhookProvisioningStatus.NOT_CONFIGURED,
        "webhook_last_error": bot.webhook_last_error,
        "webhook_last_synced_at": (
            bot.webhook_last_synced_at.isoformat() if bot.webhook_last_synced_at else None
        ),
    }
