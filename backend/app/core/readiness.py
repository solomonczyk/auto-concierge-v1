import logging
import time as time_module
from sqlalchemy import text
from app.db.session import async_session_local
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)


async def run_readiness_checks() -> tuple[dict[str, str], float]:
    """Check DB and Redis. Returns (checks dict, elapsed_ms)."""
    checks: dict[str, str] = {}
    start = time_module.monotonic()

    try:
        async with async_session_local() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        logger.error("[readiness] DB check failed: %s", exc)
        checks["db"] = f"unavailable: {type(exc).__name__}"

    try:
        redis = RedisService.get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.error("[readiness] Redis check failed: %s", exc)
        checks["redis"] = f"unavailable: {type(exc).__name__}"

    elapsed_ms = round((time_module.monotonic() - start) * 1000)
    return checks, elapsed_ms

