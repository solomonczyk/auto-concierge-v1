from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.telegram_bot import TelegramBot


async def get_active_telegram_bot_token_by_tenant_id(
    db: AsyncSession,
    tenant_id: int,
) -> str | None:
    stmt = (
        select(TelegramBot.bot_token)
        .where(
            TelegramBot.tenant_id == tenant_id,
            TelegramBot.is_active.is_(True),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_telegram_bot_token_by_username(
    db: AsyncSession,
    bot_username: str,
) -> str | None:
    stmt = (
        select(TelegramBot.bot_token)
        .where(
            TelegramBot.bot_username == bot_username,
            TelegramBot.is_active.is_(True),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_telegram_bot_for_tenant(
    db: AsyncSession,
    tenant_id: int,
    bot_token: str,
    bot_username: str | None = None,
) -> TelegramBot:
    stmt = select(TelegramBot).where(TelegramBot.tenant_id == tenant_id)

    result = await db.execute(stmt)
    bot = result.scalar_one_or_none()

    if bot is None:
        bot = TelegramBot(
            tenant_id=tenant_id,
            bot_token=bot_token,
            bot_username=bot_username,
            is_active=True,
        )
        db.add(bot)
    else:
        bot.bot_token = bot_token
        bot.bot_username = bot_username
        bot.is_active = True

    await db.commit()
    await db.refresh(bot)

    return bot


async def deactivate_telegram_bot_for_tenant(
    db: AsyncSession,
    tenant_id: int,
) -> TelegramBot | None:
    stmt = select(TelegramBot).where(TelegramBot.tenant_id == tenant_id)
    result = await db.execute(stmt)
    bot = result.scalar_one_or_none()

    if bot is None:
        return None

    bot.is_active = False
    await db.commit()
    await db.refresh(bot)
    return bot
