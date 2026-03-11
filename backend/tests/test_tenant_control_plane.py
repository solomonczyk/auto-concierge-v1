"""
Tenant Control Plane tests — list, detail, readiness, access control.
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.models import Service, Shop, Tenant, TenantStatus, User, UserRole
from app.models.telegram_bot import TelegramBot


@pytest.mark.asyncio
async def test_control_plane_list_200_superadmin(
    client_superadmin: AsyncClient,
):
    """GET /tenants/control-plane → 200 for superadmin."""
    res = await client_superadmin.get("/api/v1/tenants/control-plane")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "tenant_id" in item
        assert "name" in item
        assert "is_active" in item
        assert "shop_configured" in item
        assert "telegram_webhook_active" in item
        assert "booking_ready" in item
        assert "webhook_status" in item
        assert "webhook_last_error" in item
        assert "webhook_last_synced_at" in item


@pytest.mark.asyncio
async def test_control_plane_detail_200_superadmin(
    client_superadmin: AsyncClient,
):
    """GET /tenants/{id}/control-plane → 200 for superadmin."""
    res = await client_superadmin.get("/api/v1/tenants/1/control-plane")
    assert res.status_code == 200
    item = res.json()
    assert item["tenant_id"] == 1
    assert "name" in item
    assert "shop_configured" in item
    assert "booking_ready" in item
    assert "webhook_status" in item
    assert "webhook_last_error" in item
    assert "webhook_last_synced_at" in item


@pytest.mark.asyncio
async def test_control_plane_detail_404_not_found(
    client_superadmin: AsyncClient,
):
    """GET /tenants/{id}/control-plane → 404 if tenant not found."""
    res = await client_superadmin.get("/api/v1/tenants/99999/control-plane")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_control_plane_forbidden_non_superadmin(
    client_auth: AsyncClient,
):
    """Regular admin → 403 on control-plane list."""
    res = await client_auth.get("/api/v1/tenants/control-plane")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_control_plane_detail_forbidden_non_superadmin(
    client_auth: AsyncClient,
):
    """Regular admin → 403 on control-plane detail."""
    res = await client_auth.get("/api/v1/tenants/1/control-plane")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_readiness_empty_tenant(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """Empty tenant (no shop, services, bot) → all readiness flags false."""
    tenant = Tenant(
        name="Empty Tenant",
        status=TenantStatus.ACTIVE,
        tariff_plan_id=1,
    )
    db_session.add(tenant)
    await db_session.flush()
    tid = tenant.id
    await db_session.commit()

    res = await client_superadmin.get(f"/api/v1/tenants/{tid}/readiness")
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == tid
    assert data["shop_configured"] is False
    assert data["services_configured"] is False
    assert data["telegram_bot_registered"] is False
    assert data["telegram_webhook_active"] is False
    assert data["booking_ready"] is False


@pytest.mark.asyncio
async def test_readiness_fully_configured_tenant(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """Fully configured tenant → all readiness flags true."""
    # Tenant 1 from conftest already has shop + service; add bot with webhook_secret
    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token-123",
        bot_username="testbot",
        webhook_secret="secret123",
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    res = await client_superadmin.get("/api/v1/tenants/1/readiness")
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == 1
    assert data["shop_configured"] is True
    assert data["services_configured"] is True
    assert data["telegram_bot_registered"] is True
    assert data["telegram_webhook_active"] is True
    assert data["booking_ready"] is True


# --- Activate-bot control-plane action ---


@pytest.mark.asyncio
async def test_activate_bot_200_success(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST /tenants/{id}/control-plane/activate-bot → 200 when bot ready."""
    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username="testbot",
        webhook_secret="secret123",
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    res = await client_superadmin.post("/api/v1/tenants/1/control-plane/activate-bot")
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == 1
    assert data["action"] == "activate_bot"
    assert data["success"] is True
    assert "ready for activation" in data["message"]


@pytest.mark.asyncio
async def test_activate_bot_404_tenant_not_found(client_superadmin: AsyncClient):
    """POST /tenants/{id}/control-plane/activate-bot → 404 if tenant not found."""
    res = await client_superadmin.post("/api/v1/tenants/99999/control-plane/activate-bot")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_activate_bot_409_no_active_bot(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST /tenants/{id}/control-plane/activate-bot → 409 when no active bot."""
    tenant = Tenant(name="NoBot", status=TenantStatus.ACTIVE, tariff_plan_id=1)
    db_session.add(tenant)
    await db_session.flush()
    tid = tenant.id
    await db_session.commit()

    res = await client_superadmin.post(f"/api/v1/tenants/{tid}/control-plane/activate-bot")
    assert res.status_code == 409
    assert "No active" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_activate_bot_409_no_webhook_secret(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST /tenants/{id}/control-plane/activate-bot → 409 when bot has no webhook_secret."""
    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username="testbot",
        webhook_secret=None,
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    res = await client_superadmin.post("/api/v1/tenants/1/control-plane/activate-bot")
    assert res.status_code == 409
    assert "webhook secret" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_activate_bot_403_non_superadmin(client_auth: AsyncClient):
    """Regular admin → 403 on activate-bot."""
    res = await client_auth.post("/api/v1/tenants/1/control-plane/activate-bot")
    assert res.status_code == 403


# --- Provision-webhook control-plane action ---


@pytest.mark.asyncio
async def test_provision_webhook_200_success(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST /tenants/{id}/control-plane/provision-webhook → 200 when provisioning succeeds."""
    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username="testbot",
        webhook_secret="secret123",
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    from app.services.telegram_webhook_service import ProvisioningResult

    with patch(
        "app.api.endpoints.tenants.provision_telegram_webhook",
        new_callable=AsyncMock,
        return_value=ProvisioningResult(
            success=True,
            status="active",
            message="Telegram webhook successfully provisioned",
        ),
    ):
        res = await client_superadmin.post("/api/v1/tenants/1/control-plane/provision-webhook")
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == 1
    assert data["action"] == "provision_webhook"
    assert data["success"] is True
    assert data["status"] == "active"
    assert "successfully provisioned" in data["message"]


@pytest.mark.asyncio
async def test_provision_webhook_200_fail_response(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST /tenants/{id}/control-plane/provision-webhook → 200 with success=false when API fails."""
    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username="testbot",
        webhook_secret="secret123",
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    from app.services.telegram_webhook_service import ProvisioningResult

    with patch(
        "app.api.endpoints.tenants.provision_telegram_webhook",
        new_callable=AsyncMock,
        return_value=ProvisioningResult(
            success=False,
            status="failed",
            message="Telegram API error",
            error="Bad token",
        ),
    ):
        res = await client_superadmin.post("/api/v1/tenants/1/control-plane/provision-webhook")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["status"] == "failed"
    assert data["error"] == "Bad token"


@pytest.mark.asyncio
async def test_provision_webhook_404_tenant_not_found(client_superadmin: AsyncClient):
    """POST /tenants/{id}/control-plane/provision-webhook → 404 if tenant not found."""
    res = await client_superadmin.post("/api/v1/tenants/99999/control-plane/provision-webhook")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_provision_webhook_409_no_active_bot(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST /tenants/{id}/control-plane/provision-webhook → 409 when no active bot."""
    tenant = Tenant(name="NoBot", status=TenantStatus.ACTIVE, tariff_plan_id=1)
    db_session.add(tenant)
    await db_session.flush()
    tid = tenant.id
    await db_session.commit()

    res = await client_superadmin.post(f"/api/v1/tenants/{tid}/control-plane/provision-webhook")
    assert res.status_code == 409
    assert "No active" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_provision_webhook_409_no_webhook_secret(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST /tenants/{id}/control-plane/provision-webhook → 409 when bot has no webhook_secret."""
    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username="testbot",
        webhook_secret=None,
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    res = await client_superadmin.post("/api/v1/tenants/1/control-plane/provision-webhook")
    assert res.status_code == 409
    assert "webhook secret" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_provision_webhook_403_non_superadmin(client_auth: AsyncClient):
    """Regular admin → 403 on provision-webhook."""
    res = await client_auth.post("/api/v1/tenants/1/control-plane/provision-webhook")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_provision_webhook_409_no_bot_username(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST /tenants/{id}/control-plane/provision-webhook → 409 when bot has no username."""
    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username=None,
        webhook_secret="secret123",
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    res = await client_superadmin.post("/api/v1/tenants/1/control-plane/provision-webhook")
    assert res.status_code == 409
    assert "username" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_provision_webhook_success_sets_webhook_status_active(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """Provision success → bot.webhook_status=active in DB."""
    from unittest.mock import MagicMock

    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username="testbot",
        webhook_secret="secret123",
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"ok": True}

    with patch("app.services.telegram_webhook_service.httpx.AsyncClient") as MockClient:
        mock_post = AsyncMock(return_value=mock_resp)
        MockClient.return_value.__aenter__.return_value.post = mock_post

        res = await client_superadmin.post("/api/v1/tenants/1/control-plane/provision-webhook")

    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["status"] == "active"

    from sqlalchemy import select

    db_session.expire_all()
    refreshed = (
        await db_session.execute(
            select(TelegramBot).where(TelegramBot.tenant_id == 1, TelegramBot.is_active.is_(True))
        )
    ).scalars().first()
    assert refreshed is not None
    assert refreshed.webhook_status == "active"
    assert refreshed.webhook_last_error is None
    assert refreshed.webhook_last_synced_at is not None


@pytest.mark.asyncio
async def test_provision_webhook_fail_sets_webhook_status_failed(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """Provision fail → bot.webhook_status=failed, webhook_last_error set in DB."""
    from unittest.mock import MagicMock

    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username="testbot",
        webhook_secret="secret123",
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"ok": False, "description": "Bad token"}

    with patch("app.services.telegram_webhook_service.httpx.AsyncClient") as MockClient:
        mock_post = AsyncMock(return_value=mock_resp)
        MockClient.return_value.__aenter__.return_value.post = mock_post

        res = await client_superadmin.post("/api/v1/tenants/1/control-plane/provision-webhook")

    assert res.status_code == 200
    assert res.json()["success"] is False
    assert res.json()["status"] == "failed"
    assert "Bad token" in (res.json().get("error") or "")

    from sqlalchemy import select

    db_session.expire_all()
    refreshed = (
        await db_session.execute(
            select(TelegramBot).where(TelegramBot.tenant_id == 1, TelegramBot.is_active.is_(True))
        )
    ).scalars().first()
    assert refreshed is not None
    assert refreshed.webhook_status == "failed"
    assert refreshed.webhook_last_error == "Bad token"
    assert refreshed.webhook_last_synced_at is not None
