"""
Bot loader — creates Bot, Dispatcher with Redis FSM storage.
"""
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from app.core.config import settings


def _make_storage() -> RedisStorage | None:
    """Build FSM storage backed by Redis. Falls back to memory if Redis is unavailable."""
    try:
        storage = RedisStorage.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/1"
        )
        return storage
    except Exception as e:
        logging.warning(f"Redis FSM storage unavailable, using MemoryStorage: {e}")
        return None


try:
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
except Exception:
    logging.warning("INVALID BOT TOKEN. Bot features will be disabled.")
    bot = None

_storage = _make_storage()

if _storage:
    dp = Dispatcher(storage=_storage)
else:
    from aiogram.fsm.storage.memory import MemoryStorage
    dp = Dispatcher(storage=MemoryStorage())
