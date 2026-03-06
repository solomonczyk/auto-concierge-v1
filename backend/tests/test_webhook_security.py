import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock

from app.api.endpoints import webhook as webhook_endpoint


@pytest.mark.asyncio
async def test_webhook_503_in_production_when_secret_missing(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Webhook must be blocked in production if secret is not configured."""
    monkeypatch.setattr(webhook_endpoint.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(webhook_endpoint.settings, "TELEGRAM_WEBHOOK_SECRET", None)

    feed_update_mock = AsyncMock()
    monkeypatch.setattr(webhook_endpoint.dp, "feed_update", feed_update_mock)

    redis_get_mock = MagicMock()
    monkeypatch.setattr(webhook_endpoint.RedisService, "get_redis", redis_get_mock)

    response = await client.post(
        "/api/v1/webhook",
        json={"update_id": 123456, "message": {"text": "/start"}},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Webhook secret is not configured"

    # No webhook payload processing should happen.
    redis_get_mock.assert_not_called()
    feed_update_mock.assert_not_awaited()
