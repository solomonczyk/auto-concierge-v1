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
        "/api/v1/webhook/test_bot",
        json={"update_id": 123456, "message": {"text": "/start"}},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Webhook secret is not configured"

    redis_get_mock.assert_not_called()
    feed_update_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_403_when_secret_required_but_header_missing(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Webhook must return 403 when secret is set but header is missing."""
    monkeypatch.setattr(webhook_endpoint.settings, "TELEGRAM_WEBHOOK_SECRET", "my-secret-token")

    response = await client.post(
        "/api/v1/webhook/test_bot",
        json={"update_id": 123456, "message": {"text": "/start"}},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


@pytest.mark.asyncio
async def test_webhook_403_when_secret_required_but_header_wrong(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Webhook must return 403 when secret is set but header value is wrong."""
    monkeypatch.setattr(webhook_endpoint.settings, "TELEGRAM_WEBHOOK_SECRET", "my-secret-token")

    response = await client.post(
        "/api/v1/webhook/test_bot",
        json={"update_id": 123456, "message": {"text": "/start"}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


@pytest.mark.asyncio
async def test_webhook_200_when_secret_correct(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Webhook must succeed when secret is set and header is correct."""
    monkeypatch.setattr(webhook_endpoint.settings, "TELEGRAM_WEBHOOK_SECRET", "my-secret-token")

    feed_update_mock = AsyncMock()
    monkeypatch.setattr(webhook_endpoint.dp, "feed_update", feed_update_mock)

    redis_mock = MagicMock()
    redis_mock.exists = AsyncMock(return_value=False)
    redis_mock.set = AsyncMock(return_value=True)
    monkeypatch.setattr(webhook_endpoint.RedisService, "get_redis", MagicMock(return_value=redis_mock))

    get_token_mock = AsyncMock(return_value="123:TEST")
    monkeypatch.setattr(webhook_endpoint, "get_active_telegram_bot_token_by_username", get_token_mock)
    fake_bot = MagicMock()
    monkeypatch.setattr(webhook_endpoint.bot_registry, "get_bot", MagicMock(return_value=fake_bot))

    response = await client.post(
        "/api/v1/webhook/test_bot",
        json={
            "update_id": 123456,
            "message": {
                "message_id": 1,
                "date": 1709800000,
                "chat": {"id": 123456, "type": "private"},
                "text": "/start",
            },
        },
        headers={"X-Telegram-Bot-Api-Secret-Token": "my-secret-token"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    feed_update_mock.assert_awaited_once()
