"""
Telegram webhook provisioning service — real setWebhook API calls and operational state.

Retry-safe: each call re-invokes Telegram API, updates webhook_status,
overwrites webhook_last_error, updates webhook_last_synced_at.
Repeated provision-webhook calls do not break state; idempotent retries supported.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.telegram_bot import TelegramBot, WebhookProvisioningStatus

logger = logging.getLogger(__name__)


@dataclass
class ProvisioningResult:
    success: bool
    status: str
    message: str
    error: str | None = None


async def provision_telegram_webhook(
    db: AsyncSession,
    bot: TelegramBot,
) -> ProvisioningResult:
    """
    Call Telegram setWebhook API and update bot provisioning state.
    Caller must ensure: tenant exists, bot is active, bot has webhook_secret.
    """
    now = datetime.now(timezone.utc)
    base = (settings.SITE_URL or "").strip().rstrip("/")
    if not base:
        bot.webhook_status = WebhookProvisioningStatus.FAILED
        bot.webhook_last_error = "SITE_URL is required for Telegram webhook provisioning"
        bot.webhook_last_synced_at = now
        await db.commit()
        return ProvisioningResult(
            success=False,
            status=WebhookProvisioningStatus.FAILED,
            message="Webhook base URL is not configured",
            error="SITE_URL is required for Telegram webhook provisioning",
        )

    webhook_path = f"{settings.API_V1_STR}/webhook/{bot.bot_username.strip()}"
    webhook_url = f"{base}{webhook_path}"

    api_url = f"https://api.telegram.org/bot{bot.bot_token}/setWebhook"
    payload = {"url": webhook_url, "secret_token": bot.webhook_secret}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(api_url, json=payload)
    except Exception as e:
        err_msg = str(e)
        logger.exception("[TelegramWebhook] setWebhook failed: %s", e)
        bot.webhook_status = WebhookProvisioningStatus.FAILED
        bot.webhook_last_error = err_msg
        bot.webhook_last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        return ProvisioningResult(
            success=False,
            status=WebhookProvisioningStatus.FAILED,
            message="Failed to reach Telegram API",
            error=err_msg,
        )

    data: dict = {}
    if resp.headers.get("content-type", "").startswith("application/json"):
        try:
            data = resp.json()
        except Exception as e:
            err_msg = f"Invalid JSON from Telegram API: {e}"
            logger.warning("[TelegramWebhook] %s", err_msg)
            bot.webhook_status = WebhookProvisioningStatus.FAILED
            bot.webhook_last_error = err_msg
            bot.webhook_last_synced_at = datetime.now(timezone.utc)
            await db.commit()
            return ProvisioningResult(
                success=False,
                status=WebhookProvisioningStatus.FAILED,
                message="Invalid response from Telegram API",
                error=err_msg,
            )

    now = datetime.now(timezone.utc)

    if resp.status_code >= 400:
        err_desc = data.get("description") or f"Telegram HTTP {resp.status_code}"
        bot.webhook_status = WebhookProvisioningStatus.FAILED
        bot.webhook_last_error = err_desc
        bot.webhook_last_synced_at = now
        await db.commit()
        logger.warning(
            "[TelegramWebhook] HTTP error: bot_id=%s tenant_id=%s status=%s error=%s",
            bot.id,
            bot.tenant_id,
            resp.status_code,
            err_desc,
        )
        return ProvisioningResult(
            success=False,
            status=WebhookProvisioningStatus.FAILED,
            message="Telegram API HTTP error",
            error=err_desc,
        )

    content_type = resp.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        err_desc = f"Unexpected Telegram content-type: {content_type or 'unknown'}"
        bot.webhook_status = WebhookProvisioningStatus.FAILED
        bot.webhook_last_error = err_desc
        bot.webhook_last_synced_at = now
        await db.commit()
        logger.warning(
            "[TelegramWebhook] Non-JSON response: bot_id=%s tenant_id=%s content_type=%s",
            bot.id,
            bot.tenant_id,
            content_type,
        )
        return ProvisioningResult(
            success=False,
            status=WebhookProvisioningStatus.FAILED,
            message="Unexpected response from Telegram API",
            error=err_desc,
        )

    if data.get("ok"):
        bot.webhook_status = WebhookProvisioningStatus.ACTIVE
        bot.webhook_last_error = None
        bot.webhook_last_synced_at = now
        await db.commit()

        logger.info(
            "[TelegramWebhook] Provisioned: bot_id=%s tenant_id=%s webhook=%s",
            bot.id,
            bot.tenant_id,
            webhook_url,
        )
        return ProvisioningResult(
            success=True,
            status=WebhookProvisioningStatus.ACTIVE,
            message="Telegram webhook successfully provisioned",
        )

    err_desc = data.get("description", "Telegram setWebhook failed")
    bot.webhook_status = WebhookProvisioningStatus.FAILED
    bot.webhook_last_error = err_desc
    bot.webhook_last_synced_at = now
    await db.commit()

    logger.warning(
        "[TelegramWebhook] Failed: bot_id=%s tenant_id=%s error=%s",
        bot.id,
        bot.tenant_id,
        err_desc,
    )
    return ProvisioningResult(
        success=False,
        status=WebhookProvisioningStatus.FAILED,
        message="Telegram API error",
        error=err_desc,
    )


# TODO (future-ops layer): async job / outbox for provisioning; retries with backoff;
# reconciliation via getWebhookInfo; drift detection between DB and Telegram.
