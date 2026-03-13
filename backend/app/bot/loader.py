"""
Centralized Telegram runtime bootstrap:
- builds FSM storage
- creates shared Dispatcher
- attaches handler graph exactly once
"""
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from app.core.config import settings
from app.bot.handlers import router as bot_router

logger = logging.getLogger(__name__)


def _make_storage() -> RedisStorage | None:
    """Build FSM storage backed by Redis. Falls back to memory if Redis is unavailable."""
    try:
        return RedisStorage.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1"
        )
    except Exception as e:
        logger.warning("Redis FSM storage unavailable, using MemoryStorage: %s", e)
        return None


def _build_dispatcher() -> Dispatcher:
    storage = _make_storage()
    if storage:
        dispatcher = Dispatcher(storage=storage)
    else:
        from aiogram.fsm.storage.memory import MemoryStorage

        dispatcher = Dispatcher(storage=MemoryStorage())

    dispatcher.include_router(bot_router)
    logger.info("Telegram dispatcher graph initialized")
    return dispatcher


dp = _build_dispatcher()
