"""
Control Plane smoke tests — admin endpoints (SUPERADMIN only).
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_summary_200_superadmin(client_superadmin: AsyncClient):
    """GET /admin/control-plane/summary → 200 for superadmin."""
    res = await client_superadmin.get("/api/v1/admin/control-plane/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_tenants" in data
    assert "active_tenants" in data
    assert "pending_tenants" in data
    assert "ready_tenants" in data
    assert "tenants_without_shop" in data


@pytest.mark.asyncio
async def test_summary_403_non_superadmin(client_auth: AsyncClient):
    """Non-superadmin → 403 on summary."""
    res = await client_auth.get("/api/v1/admin/control-plane/summary")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_overview_200_superadmin(client_superadmin: AsyncClient):
    """GET /admin/tenants/overview → 200, returns tenants list."""
    res = await client_superadmin.get("/api/v1/admin/tenants/overview")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "tenant_id" in item
        assert "name" in item
        assert "slug" in item
        assert "status" in item
        assert "shop_configured" in item
        assert "services_configured" in item
        assert "telegram_bot_registered" in item
        assert "telegram_webhook_active" in item
        assert "booking_ready" in item


@pytest.mark.asyncio
async def test_overview_403_non_superadmin(client_auth: AsyncClient):
    """Non-superadmin → 403 on overview."""
    res = await client_auth.get("/api/v1/admin/tenants/overview")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_tenant_detail_200_superadmin(client_superadmin: AsyncClient):
    """GET /admin/tenants/{id} → 200, expected structure."""
    res = await client_superadmin.get("/api/v1/admin/tenants/1")
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == 1
    assert "name" in data
    assert "status" in data
    assert "onboarding_state" in data
    assert "readiness" in data
    assert "shop" in data
    assert "services_count" in data
    assert "telegram_bot" in data
    assert "booking_ready" in data["readiness"]


@pytest.mark.asyncio
async def test_tenant_detail_404(client_superadmin: AsyncClient):
    """GET /admin/tenants/99999 → 404."""
    res = await client_superadmin.get("/api/v1/admin/tenants/99999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_tenant_detail_403_non_superadmin(client_auth: AsyncClient):
    """Non-superadmin → 403 on tenant detail."""
    res = await client_auth.get("/api/v1/admin/tenants/1")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_activate_bot_protected(client_superadmin: AsyncClient):
    """POST /admin/tenants/{id}/activate-bot → 200 or 409 (protected, works)."""
    res = await client_superadmin.post("/api/v1/admin/tenants/1/activate-bot")
    assert res.status_code in (200, 409)
    if res.status_code == 200:
        data = res.json()
        assert data["tenant_id"] == 1
        assert data["action"] == "activate_bot"
        assert data["success"] is True


@pytest.mark.asyncio
async def test_activate_bot_403_non_superadmin(client_auth: AsyncClient):
    """Non-superadmin → 403 on activate-bot."""
    res = await client_auth.post("/api/v1/admin/tenants/1/activate-bot")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_provision_webhook_protected(client_superadmin: AsyncClient):
    """POST /admin/tenants/{id}/provision-webhook → 200 or 409 (protected, works)."""
    res = await client_superadmin.post("/api/v1/admin/tenants/1/provision-webhook")
    assert res.status_code in (200, 409)
    if res.status_code == 200:
        data = res.json()
        assert data["tenant_id"] == 1
        assert data["action"] == "provision_webhook"
        assert "success" in data


@pytest.mark.asyncio
async def test_provision_webhook_403_non_superadmin(client_auth: AsyncClient):
    """Non-superadmin → 403 on provision-webhook."""
    res = await client_auth.post("/api/v1/admin/tenants/1/provision-webhook")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_finalize_onboarding_protected(client_superadmin: AsyncClient):
    """POST /admin/tenants/{id}/finalize-onboarding → 200 or 400 (protected, works)."""
    res = await client_superadmin.post("/api/v1/admin/tenants/1/finalize-onboarding")
    assert res.status_code in (200, 400)
    if res.status_code == 200:
        data = res.json()
        assert data["tenant_id"] == 1
        assert data["action"] == "finalize_onboarding"
        assert data["finalized"] is True


@pytest.mark.asyncio
async def test_finalize_onboarding_403_non_superadmin(client_auth: AsyncClient):
    """Non-superadmin → 403 on finalize-onboarding."""
    res = await client_auth.post("/api/v1/admin/tenants/1/finalize-onboarding")
    assert res.status_code == 403
