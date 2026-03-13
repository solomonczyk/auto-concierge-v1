"""
Centralized Telegram runtime bootstrap:
- builds FSM storage (Redis)
- creates shared Dispatcher
- attaches handler graph exactly once
"""
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from app.core.config import settings
from app.bot.handlers import router as bot_router

logger = logging.getLogger(__name__)

# aiogram storage switched to redis
storage = RedisStorage.from_url(settings.REDIS_URL_RESOLVED)
dp = Dispatcher(storage=storage)
dp.include_router(bot_router)
logger.info("Telegram dispatcher graph initialized")
