import logging
from typing import Awaitable, Callable

from sqlalchemy import text

from app.bot.client import get_bot
from app.db.session import async_session_local
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)

HealthCheckFn = Callable[[], Awaitable[str]]


async def check_db() -> str:
    try:
        async with async_session_local() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        logger.error("[health] DB check failed: %s", exc)
        return f"unavailable: {type(exc).__name__}"


async def check_redis() -> str:
    try:
        redis = RedisService.get_redis()
        await redis.ping()
        return "ok"
    except Exception as exc:
        logger.error("[health] Redis check failed: %s", exc)
        return f"unavailable: {type(exc).__name__}"


async def check_telegram_init() -> str:
    try:
        bot = get_bot()
        if bot is None:
            return "unavailable: BotNotConfigured"
        return "ok"
    except Exception as exc:
        logger.error("[health] Telegram init check failed: %s", exc)
        return f"unavailable: {type(exc).__name__}"


HEALTH_CHECKS: dict[str, HealthCheckFn] = {
    "db": check_db,
    "redis": check_redis,
    "telegram_init": check_telegram_init,
}

