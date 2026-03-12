"""
SaaS Provisioning / Onboarding Layer tests.
Covers: tenant create, duplicate slug, tariff, bot registration, webhook, onboarding state, finalization.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Tenant, TenantStatus
from app.models.telegram_bot import TelegramBot


@pytest.mark.asyncio
async def test_tenant_create_success_returns_id_name_slug_status(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST /tenants → 201, response has id, name, slug, status (PENDING)."""
    res = await client_superadmin.post(
        "/api/v1/tenants",
        json={
            "name": "Acme Auto",
            "slug": "acme-auto",
            "admin_username": "acmeadmin",
            "admin_password": "securepass123",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert data["name"] == "Acme Auto"
    assert data["slug"] == "acme-auto"
    assert data["status"] == "pending"
    assert data["id"] == data.get("tenant_id")


@pytest.mark.asyncio
async def test_tenant_create_duplicate_slug_409(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """Duplicate slug → 409 Conflict."""
    await client_superadmin.post(
        "/api/v1/tenants",
        json={
            "name": "First",
            "slug": "dup-slug",
            "admin_username": "user1",
            "admin_password": "pass12345",
        },
    )
    res = await client_superadmin.post(
        "/api/v1/tenants",
        json={
            "name": "Second",
            "slug": "dup-slug",
            "admin_username": "user2",
            "admin_password": "pass12345",
        },
    )
    assert res.status_code == 409
    assert "already exists" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_tariff_assign_200(
    client_superadmin: AsyncClient,
):
    """POST /tenants/1/tariff → 200, tariff assigned."""
    res = await client_superadmin.post(
        "/api/v1/tenants/1/tariff",
        json={"tariff_code": "starter"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == 1
    assert data["tariff_code"] == "starter"
    assert "tariff_plan_id" in data


@pytest.mark.asyncio
async def test_tariff_assign_404_tenant_not_found(client_superadmin: AsyncClient):
    """POST /tenants/99999/tariff → 404."""
    res = await client_superadmin.post(
        "/api/v1/tenants/99999/tariff",
        json={"tariff_code": "starter"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_bot_register_201(
    client_superadmin: AsyncClient,
):
    """POST /tenants/1/bots → 201, bot registered."""
    res = await client_superadmin.post(
        "/api/v1/tenants/1/bots",
        json={"bot_token": "123:ABC", "bot_username": "TestBot"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["tenant_id"] == 1
    assert data["bot_username"] == "TestBot"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_bot_register_duplicate_updates_no_duplicate_record(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """Re-register same tenant bot → 200, same bot updated (no second record)."""
    await client_superadmin.post(
        "/api/v1/tenants/1/bots",
        json={"bot_token": "111:AAA", "bot_username": "SameBot"},
    )
    res = await client_superadmin.post(
        "/api/v1/tenants/1/bots",
        json={"bot_token": "222:BBB", "bot_username": "SameBot"},
    )
    assert res.status_code == 201
    count = (await db_session.execute(select(TelegramBot).where(TelegramBot.tenant_id == 1))).scalars().all()
    assert len(count) == 1


@pytest.mark.asyncio
async def test_webhook_provisioning_returns_url_and_secret_present(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """POST /tenants/1/bots/{bot_id}/webhook → 200, webhook_url and webhook_secret_present."""
    from unittest.mock import AsyncMock
    from app.services.telegram_webhook_service import ProvisioningResult

    bot = TelegramBot(
        tenant_id=1,
        bot_token="test-token",
        bot_username="webhookbot",
        is_active=True,
    )
    db_session.add(bot)
    await db_session.commit()
    await db_session.refresh(bot)
    bot_id = bot.id

    monkeypatch.setattr(
        "app.api.endpoints.telegram_bots.provision_telegram_webhook",
        AsyncMock(return_value=ProvisioningResult(success=True, status="active", message="OK")),
    )
    res = await client_superadmin.post(f"/api/v1/tenants/1/bots/{bot_id}/webhook")
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == 1
    assert data["bot_id"] == bot_id
    assert "webhook_url" in data
    assert "webhook_secret_present" in data


@pytest.mark.asyncio
async def test_onboarding_endpoint_returns_progress(
    client_superadmin: AsyncClient,
):
    """GET /tenants/1/onboarding → 200, tenant_created, tariff_assigned, ..., onboarding_complete, missing_steps."""
    res = await client_superadmin.get("/api/v1/tenants/1/onboarding")
    assert res.status_code == 200
    data = res.json()
    assert data["tenant_id"] == 1
    assert "tenant_created" in data
    assert "tariff_assigned" in data
    assert "telegram_bot_registered" in data
    assert "webhook_provisioned" in data
    assert "readiness_ok" in data
    assert "onboarding_complete" in data
    assert "missing_steps" in data
    assert isinstance(data["missing_steps"], list)


@pytest.mark.asyncio
async def test_onboarding_finalize_when_incomplete_400(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """POST .../onboarding/finalize when incomplete → 400."""
    tenant = Tenant(name="New", slug="new-tenant", status=TenantStatus.PENDING, tariff_plan_id=1)
    db_session.add(tenant)
    await db_session.flush()
    tid = tenant.id
    await db_session.commit()

    res = await client_superadmin.post(f"/api/v1/tenants/{tid}/onboarding/finalize")
    assert res.status_code == 400
    assert "incomplete" in res.json().get("detail", "").lower() or "missing" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_onboarding_finalize_when_complete_sets_active(
    client_superadmin: AsyncClient,
    db_session: AsyncSession,
):
    """When onboarding complete, finalize → tenant becomes ACTIVE."""
    from app.models.models import Shop, Service
    tenant = Tenant(name="Final", slug="final-tenant", status=TenantStatus.PENDING, tariff_plan_id=1)
    db_session.add(tenant)
    await db_session.flush()
    tid = tenant.id
    shop = Shop(tenant_id=tid, name="S", address="A")
    db_session.add(shop)
    await db_session.flush()
    db_session.add(Service(tenant_id=tid, name="X", duration_minutes=30, base_price=100))
    bot = TelegramBot(
        tenant_id=tid,
        bot_token="x:y",
        bot_username="b",
        is_active=True,
        webhook_secret="sec",
        webhook_status="active",
    )
    db_session.add(bot)
    await db_session.commit()

    res = await client_superadmin.post(f"/api/v1/tenants/{tid}/onboarding/finalize")
    assert res.status_code == 200
    data = res.json()
    assert data.get("finalized") is True

    db_session.expire_all()
    t = await db_session.get(Tenant, tid)
    assert t is not None
    assert t.status == TenantStatus.ACTIVE
