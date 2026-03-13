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

    # 1. Validate secret (before parsing body / bot lookup)
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    if expected_secret and expected_secret.strip():
        if not x_telegram_bot_api_secret_token or not secrets.compare_digest(
            x_telegram_bot_api_secret_token, expected_secret
        ):
            WEBHOOK_REJECTED_TOTAL.labels(reason="forbidden").inc()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    elif settings.ENVIRONMENT == "production":
        WEBHOOK_REJECTED_TOTAL.labels(reason="no_secret").inc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret is not configured",
        )

    telegram_update = Update(**update)
    update_id = telegram_update.update_id

    async with async_session_local() as db:
        # 2. Bot lookup
        tg_bot = await get_active_telegram_bot_by_username(db, bot_username)

        # 3. Unknown bot
        if not tg_bot:
            logger.warning("Webhook received for unknown bot: %s", bot_username)
            return {"status": "ok"}

        # Per-bot secret (overrides global if set)
        expected_secret = tg_bot.webhook_secret or settings.TELEGRAM_WEBHOOK_SECRET
        if not expected_secret or not expected_secret.strip():
            WEBHOOK_REJECTED_TOTAL.labels(reason="no_secret").inc()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Webhook secret is not configured",
            )
        if not x_telegram_bot_api_secret_token or not secrets.compare_digest(
            x_telegram_bot_api_secret_token, expected_secret
        ):
            WEBHOOK_REJECTED_TOTAL.labels(reason="forbidden").inc()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

        # Lifecycle guard: reject webhook for non-operational tenant
        from app.services.tenant_lifecycle_guard import check_tenant_operational_status
        operational, _ = await check_tenant_operational_status(db, tg_bot.tenant_id)
        if not operational:
            WEBHOOK_REJECTED_TOTAL.labels(reason="tenant_inactive").inc()
            logger.info(
                "webhook.rejected",
                extra={"reason": "tenant_inactive", "tenant_id": tg_bot.tenant_id, "bot_username": bot_username},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant is suspended or disabled",
            )

        key = f"telegram_update:{tg_bot.id}:{update_id}"
        redis = RedisService.get_redis()
        if await redis.exists(key):
            return {"msg": "already_processed"}

        bot = bot_registry.get_bot(tg_bot.bot_token)
        try:
            if tg_bot.bot_token.startswith("123456:TEST_TOKEN"):
                # E2E test bot — skip feed_update to avoid Telegram API calls (Unauthorized)
                pass
            else:
                await dp.feed_update(bot, telegram_update)
            await redis.set(key, "1", ex=86400)
            WEBHOOK_PROCESSED_TOTAL.inc()
        except Exception as e:
            logger.exception("webhook.processing_failed")
            raise HTTPException(status_code=500, detail="webhook processing failed") from e
        return {"status": "ok"}
