"""
Minimal Telegram Bot client. Only Bot instance, no Dispatcher, no storage.
Used by NotificationService, worker, and any code that needs to send messages.
"""
import logging

from aiogram import Bot

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
except Exception as e:
    logger.warning("INVALID BOT TOKEN. Bot features will be disabled: %s", e)
    bot = None
