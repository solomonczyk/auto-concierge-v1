"""
Tenant Control Plane tests — list, detail, readiness, access control.
"""
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
        assert "services_configured" in item
        assert "telegram_bot_registered" in item
        assert "telegram_webhook_active" in item
        assert "booking_ready" in item


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
