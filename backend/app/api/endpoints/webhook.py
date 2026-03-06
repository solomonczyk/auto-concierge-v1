import secrets
from fastapi import APIRouter, Header, HTTPException, status
from aiogram.types import Update
from app.services.redis_service import RedisService

from app.bot.loader import bot, dp
from app.core.config import settings

router = APIRouter()

@router.post("/webhook")
async def bot_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None)
):
    # Defense in depth: do not accept Telegram updates in production
    # when webhook secret is not configured.
    if settings.is_production and not settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret is not configured",
        )

    if settings.TELEGRAM_WEBHOOK_SECRET:
        if not x_telegram_bot_api_secret_token or not secrets.compare_digest(
            x_telegram_bot_api_secret_token,
            settings.TELEGRAM_WEBHOOK_SECRET
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    telegram_update = Update(**update)
    
    # Idempotency Check
    redis = RedisService.get_redis()
    update_id = telegram_update.update_id
    key = f"telegram_update:{update_id}"
    
    if await redis.exists(key):
        return {"status": "ok", "msg": "already_processed"}
    
    await redis.set(key, "1", ex=86400) # Expire in 24 hours
    
    await dp.feed_update(bot, telegram_update)
    return {"status": "ok"}
