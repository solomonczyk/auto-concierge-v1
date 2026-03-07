import logging
import secrets
from fastapi import APIRouter, Header, HTTPException, Request, status
from aiogram.types import Update
from app.services.redis_service import RedisService
from app.core.rate_limit import limiter
from app.core.metrics import (
    WEBHOOK_REQUESTS_TOTAL,
    WEBHOOK_REJECTED_TOTAL,
    WEBHOOK_PROCESSED_TOTAL,
)

from app.bot.loader import bot, dp
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook")
@limiter.limit("120/minute")
async def bot_webhook(
    request: Request,
    update: dict,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    rid = getattr(request.state, "request_id", None) or "-"
    logger.info(
        "webhook.request",
        extra={"request_id": rid, "update_id": update.get("update_id")},
    )
    WEBHOOK_REQUESTS_TOTAL.inc()

    if settings.is_production and not settings.TELEGRAM_WEBHOOK_SECRET:
        WEBHOOK_REJECTED_TOTAL.labels(reason="no_secret").inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret is not configured",
        )

    if settings.TELEGRAM_WEBHOOK_SECRET:
        if not x_telegram_bot_api_secret_token or not secrets.compare_digest(
            x_telegram_bot_api_secret_token,
            settings.TELEGRAM_WEBHOOK_SECRET,
        ):
            WEBHOOK_REJECTED_TOTAL.labels(reason="forbidden").inc()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )

    telegram_update = Update(**update)

    redis = RedisService.get_redis()
    update_id = telegram_update.update_id
    key = f"telegram_update:{update_id}"

    if await redis.exists(key):
        return {"status": "ok", "msg": "already_processed"}

    await redis.set(key, "1", ex=86400)

    await dp.feed_update(bot, telegram_update)
    WEBHOOK_PROCESSED_TOTAL.inc()
    return {"status": "ok"}
