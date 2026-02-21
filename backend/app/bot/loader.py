from aiogram import Bot, Dispatcher
from app.core.config import settings
import logging

try:
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
except Exception:
    logging.warning("INVALID BOT TOKEN. Bot features will be disabled.")
    bot = None
dp = Dispatcher()
