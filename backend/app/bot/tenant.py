"""
Multi-tenant helpers for Telegram bot.
Provides tenant resolution and context management.
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import tenant_id_context
from app.core.security import get_token_hash, encrypt_token
from app.core.config import settings
from app.models.models import Tenant, TariffPlan


async def get_or_create_tenant(
    db: AsyncSession,
    bot_token: str | None = None,
) -> Tenant:
    """
    Resolve tenant by Telegram bot token.

    New flow:
    1) try telegram_bots.bot_token -> tenant_id
    2) fallback to legacy tenants.bot_token_hash
    3) if still not found, create legacy tenant
    """
    from app.models.telegram_bot import TelegramBot

    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise ValueError("Telegram bot token is required for tenant resolution")

    # 1. New DB-backed mapping
    telegram_bot_stmt = (
        select(TelegramBot)
        .where(
            TelegramBot.bot_token == token,
            TelegramBot.is_active.is_(True),
        )
        .limit(1)
    )
    telegram_bot_result = await db.execute(telegram_bot_stmt)
    telegram_bot = telegram_bot_result.scalar_one_or_none()

    tenant = None

    if telegram_bot is not None:
        tenant_stmt = select(Tenant).where(Tenant.id == telegram_bot.tenant_id)
        tenant_result = await db.execute(tenant_stmt)
        tenant = tenant_result.scalar_one_or_none()

    # 2. Legacy fallback
    if tenant is None:
        token_hash = get_token_hash(token)
        legacy_stmt = select(Tenant).where(Tenant.bot_token_hash == token_hash)
        legacy_result = await db.execute(legacy_stmt)
        tenant = legacy_result.scalar_one_or_none()

        # 3. Legacy autocreate
        if tenant is None:
            tariff_stmt = select(TariffPlan).where(TariffPlan.name == "free")
            tariff_result = await db.execute(tariff_stmt)
            free_tariff = tariff_result.scalar_one_or_none()

            tenant = Tenant(
                name="Default Service",
                encrypted_bot_token=encrypt_token(token),
                bot_token_hash=token_hash,
                tariff_plan_id=free_tariff.id if free_tariff else None,
            )
            db.add(tenant)
            await db.commit()
            await db.refresh(tenant)

    tenant_id_context.set(tenant.id)

    if not db.in_transaction():
        await db.begin()

    await db.execute(text("SET LOCAL app.current_tenant_id = :tenant_id"), {"tenant_id": str(tenant.id)})

    return tenant


async def get_or_create_tenant_from_bot(
    db: AsyncSession,
    bot,
) -> Tenant:
    bot_token = getattr(bot, "token", None)
    return await get_or_create_tenant(db, bot_token=bot_token)


async def get_tenant_shop(db: AsyncSession, tenant: Tenant):
    """
    Get the first shop for a tenant.
    Used for MVP where each tenant has one shop.
    """
    from app.models.models import Shop
    
    stmt = select(Shop).where(Shop.tenant_id == tenant.id).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
