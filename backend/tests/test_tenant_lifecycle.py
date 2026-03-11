"""
Tenant Lifecycle / Billing Control tests.
Covers: status update, lifecycle endpoint, public booking guard, webhook guard.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Tenant, TenantStatus


@pytest.mark.asyncio
async def test_status_update_200_superadmin(
    client_superadmin: AsyncClient,
):
    """PATCH /tenants/{id}/status → 200, status changes."""
    res = await client_superadmin.patch(
        "/api/v1/tenants/1/status",
        json={"status": "suspended"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == 1
    assert data["status"] == "suspended"

    # Restore ACTIVE for other tests
    res2 = await client_superadmin.patch(
        "/api/v1/tenants/1/status",
        json={"status": "active"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "active"


@pytest.mark.asyncio
async def test_status_update_404_not_found(client_superadmin: AsyncClient):
    """PATCH /tenants/{id}/status → 404 if tenant not found."""
    res = await client_superadmin.patch(
        "/api/v1/tenants/99999/status",
        json={"status": "suspended"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_lifecycle_endpoint_200(client_superadmin: AsyncClient):
    """GET /tenants/{id}/lifecycle → 200 with operational, billing_ok, readiness_ok."""
    res = await client_superadmin.get("/api/v1/tenants/1/lifecycle")
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == 1
    assert "status" in data
    assert "operational" in data
    assert "billing_ok" in data
    assert "readiness_ok" in data


@pytest.mark.asyncio
async def test_public_booking_active_tenant_allowed(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """ACTIVE tenant → public booking allowed."""
    tenant = await db_session.get(Tenant, 1)
    assert tenant is not None
    tenant.slug = "test-tenant"
    tenant.status = TenantStatus.ACTIVE
    await db_session.commit()

    res = await client.get("/api/v1/test-tenant/services/public")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_public_booking_suspended_tenant_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """SUSPENDED tenant → public booking 403."""
    tenant = await db_session.get(Tenant, 1)
    assert tenant is not None
    tenant.slug = "test-tenant"
    tenant.status = TenantStatus.SUSPENDED
    await db_session.commit()

    res = await client.get("/api/v1/test-tenant/services/public")
    assert res.status_code == 403
    assert "приостановлен" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_public_booking_disabled_tenant_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """DISABLED tenant → public booking 403."""
    tenant = await db_session.get(Tenant, 1)
    assert tenant is not None
    tenant.slug = "test-tenant"
    tenant.status = TenantStatus.DISABLED
    await db_session.commit()

    res = await client.get("/api/v1/test-tenant/services/public")
    assert res.status_code == 403
    assert "отключен" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_readiness_includes_lifecycle_fields(
    client_superadmin: AsyncClient,
):
    """GET /tenants/{id}/readiness includes tenant_status and tenant_operational."""
    res = await client_superadmin.get("/api/v1/tenants/1/readiness")
    assert res.status_code == 200
    data = res.json()
    assert "tenant_status" in data
    assert "tenant_operational" in data
    assert data["tenant_status"] == "active"
    assert data["tenant_operational"] is True


@pytest.mark.asyncio
async def test_webhook_rejects_suspended_tenant(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Webhook for suspended tenant → 403 tenant inactive."""
    from app.models.telegram_bot import TelegramBot
    from app.api.endpoints import webhook as webhook_endpoint
    from unittest.mock import AsyncMock, MagicMock

    tenant = await db_session.get(Tenant, 1)
    assert tenant is not None
    tenant.status = TenantStatus.SUSPENDED
    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username="suspended_bot",
        webhook_secret="secret123",
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    fake_redis = MagicMock()
    fake_redis.exists = AsyncMock(return_value=False)
    fake_redis.set = AsyncMock(return_value=True)
    monkeypatch.setattr(webhook_endpoint.RedisService, "get_redis", lambda: fake_redis)

    valid_update = {
        "update_id": 123,
        "message": {
            "message_id": 1,
            "date": 1709800000,
            "chat": {"id": 123456, "type": "private"},
            "text": "/start",
        },
    }
    res = await client.post(
        "/api/v1/webhook/suspended_bot",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "secret123"},
    )
    assert res.status_code == 403
    detail = res.json().get("detail", "").lower()
    assert "suspended" in detail or "disabled" in detail
