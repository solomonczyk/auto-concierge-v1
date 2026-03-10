"""
Telegram bot client accessor.

Uses BotRegistry to obtain bot instances instead of creating
a global singleton Bot.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.bot.bot_registry import bot_registry
from app.services.telegram_bot_service import (
    get_active_telegram_bot_token_by_tenant_id,
)

logger = logging.getLogger(__name__)


def get_bot():
    """
    Return default bot instance using TELEGRAM_BOT_TOKEN.
    """
    token = settings.TELEGRAM_BOT_TOKEN

    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN is not configured")
        return None

    try:
        return bot_registry.get_bot(token)
    except Exception as e:
        logger.warning("Failed to initialize Telegram bot: %s", e)
        return None


async def get_bot_by_tenant_id(
    db: AsyncSession,
    tenant_id: int,
):
    token = await get_active_telegram_bot_token_by_tenant_id(db, tenant_id)
    if not token:
        return None
    try:
        return bot_registry.get_bot(token)
    except Exception as e:
        logger.warning(
            "Failed to initialize tenant Telegram bot for tenant_id=%s: %s",
            tenant_id,
            e,
        )
        return None
