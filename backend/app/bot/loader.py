"""
Bot loader — Dispatcher, FSM storage, handlers. Bot instance from app.bot.client.
"""
import logging

from aiogram import Dispatcher
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


_storage = _make_storage()

if _storage:
    dp = Dispatcher(storage=_storage)
else:
    from aiogram.fsm.storage.memory import MemoryStorage
    dp = Dispatcher(storage=MemoryStorage())
