from app.services.redis_service import RedisService


def _jti_key(jti: str) -> str:
    return f"ws_ticket_jti:{jti}"


async def consume_jti_once(*, jti: str, ttl_seconds: int) -> bool:
    """
    Consume ws ticket jti once using Redis SET NX EX.
    Returns True on first use, False if already used.
    """
    if not jti:
        return False

    safe_ttl = max(1, int(ttl_seconds))
    redis = RedisService.get_redis()
    result = await redis.set(_jti_key(jti), "1", nx=True, ex=safe_ttl)
    return bool(result)
