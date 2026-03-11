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

from app.bot.loader import dp
from app.bot.bot_registry import bot_registry
from app.db.session import async_session_local
from app.services.telegram_bot_service import get_active_telegram_bot_by_username
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook/{bot_username}")
@limiter.limit("120/minute")
async def bot_webhook(
    bot_username: str,
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

    telegram_update = Update(**update)

    redis = RedisService.get_redis()
    update_id = telegram_update.update_id
    key = f"telegram_update:{update_id}"

    if await redis.exists(key):
        return {"status": "ok", "msg": "already_processed"}

    await redis.set(key, "1", ex=86400)

    async with async_session_local() as db:
        tg_bot = await get_active_telegram_bot_by_username(db, bot_username)

    if not tg_bot:
        WEBHOOK_REJECTED_TOTAL.labels(reason="unknown_bot").inc()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bot not found",
        )

    expected_secret = tg_bot.webhook_secret or settings.TELEGRAM_WEBHOOK_SECRET
    if not expected_secret or not expected_secret.strip():
        WEBHOOK_REJECTED_TOTAL.labels(reason="no_secret").inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret is not configured",
        )
    if not x_telegram_bot_api_secret_token or not secrets.compare_digest(
        x_telegram_bot_api_secret_token,
        expected_secret,
    ):
        WEBHOOK_REJECTED_TOTAL.labels(reason="forbidden").inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
        )

    bot = bot_registry.get_bot(tg_bot.bot_token)
    await dp.feed_update(bot, telegram_update)
    WEBHOOK_PROCESSED_TOTAL.inc()
    return {"status": "ok"}
