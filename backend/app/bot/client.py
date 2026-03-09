"""
Telegram bot client accessor.

Uses BotRegistry to obtain bot instances instead of creating
a global singleton Bot.
"""
import logging
from app.core.config import settings
from app.bot.bot_registry import bot_registry

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
