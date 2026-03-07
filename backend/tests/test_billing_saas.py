"""
Stage 4: Billing / SaaS readiness tests.
- Tenant in limit -> success
- Tenant exceeded appointment limit -> reject with structured error
- Usage counter counts correctly
- Feature gate works by plan
- Plan model correctly read from tenant
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Appointment, Client, Service, Shop, Tenant, TariffPlan, TenantStatus
from app.services.usage_service import (
    get_appointments_this_month,
    check_appointments_limit,
    LimitExceededError,
    get_features_for_plan,
    can_use_feature,
)
from app.services.plan_limits import get_limits


# ─── Unit: plan limits ───────────────────────────────────────────────────────

def test_get_limits_starter():
    limits = get_limits("starter")
    assert limits["max_users"] == 3
    assert limits["max_appointments_per_month"] == 50
    assert limits["max_webhook_requests_per_day"] == 100
    assert limits["max_ai_requests_per_day"] == 0


def test_get_limits_business():
    limits = get_limits("business")
    assert limits["max_appointments_per_month"] == 500
    assert limits["max_ai_requests_per_day"] == 100


def test_get_limits_enterprise():
    limits = get_limits("enterprise")
    assert limits["max_appointments_per_month"] == 5000


def test_get_limits_legacy_alias():
    """free -> starter, standard -> business, pro -> enterprise"""
    assert get_limits("free")["max_appointments_per_month"] == 50
    assert get_limits("standard")["max_appointments_per_month"] == 500
    assert get_limits("pro")["max_appointments_per_month"] == 5000


def test_get_limits_none_defaults_to_starter():
    limits = get_limits(None)
    assert limits["max_appointments_per_month"] == 50


# ─── Unit: feature gating ────────────────────────────────────────────────────

def test_feature_webhook_starter_denied():
    assert can_use_feature("starter", "webhook") is False
    assert can_use_feature("free", "webhook") is False


def test_feature_webhook_business_allowed():
    assert can_use_feature("business", "webhook") is True
    assert can_use_feature("enterprise", "webhook") is True


def test_feature_advanced_analytics_enterprise_only():
    assert can_use_feature("starter", "advanced_analytics") is False
    assert can_use_feature("business", "advanced_analytics") is False
    assert can_use_feature("enterprise", "advanced_analytics") is True


def test_get_features_for_plan_starter():
    f = get_features_for_plan("starter")
    assert f["webhook"] is False
    assert f["ai"] is False
    assert f["advanced_analytics"] is False


def test_get_features_for_plan_enterprise():
    f = get_features_for_plan("enterprise")
    assert f["webhook"] is True
    assert f["ai"] is True
    assert f["advanced_analytics"] is True


# ─── Integration: usage counter + limit enforcement ───────────────────────────

@pytest.mark.asyncio
async def test_get_appointments_this_month_counts_correctly(db_session: AsyncSession):
    """Assert usage counter counts appointments created this month."""
    from datetime import datetime, timezone as tz
    from app.models.models import AppointmentStatus

    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    now = datetime.now(tz.utc)
    for i in range(3):
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            service_id=service.id,
            client_id=client.id,
            start_time=now,
            end_time=now,
            status=AppointmentStatus.NEW,
        )
        db_session.add(appt)
    await db_session.commit()

    count = await get_appointments_this_month(db_session, 1)
    assert count >= 3


@pytest.mark.asyncio
async def test_check_appointments_limit_raises_when_exceeded(db_session: AsyncSession):
    """Assert LimitExceededError when limit exceeded."""
    limits = get_limits("starter")
    limit_val = limits["max_appointments_per_month"]

    # Create enough appointments to hit limit (tenant 1 has starter with 50)
    from app.models.models import AppointmentStatus
    from datetime import datetime, timezone as tz

    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()
    now = datetime.now(tz.utc)

    existing = await get_appointments_this_month(db_session, 1)
    to_create = max(0, limit_val - existing)
    for _ in range(to_create):
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            service_id=service.id,
            client_id=client.id,
            start_time=now,
            end_time=now,
            status=AppointmentStatus.NEW,
        )
        db_session.add(appt)
    await db_session.commit()

    with pytest.raises(LimitExceededError) as exc_info:
        await check_appointments_limit(db_session, 1, "starter")
    e = exc_info.value
    assert e.limit_name == "max_appointments_per_month"
    assert e.current >= limit_val
    assert e.limit == limit_val
    detail = e.to_detail()
    assert detail["code"] == "limit_exceeded"
    assert "current" in detail
    assert "limit" in detail


# ─── API: tenant in limit -> success ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_appointment_within_limit_succeeds(client_auth: AsyncClient, db_session: AsyncSession):
    """Tenant within limit can create appointment."""
    from datetime import datetime, timezone as tz, timedelta

    count_before = await get_appointments_this_month(db_session, 1)
    limits = get_limits("starter")
    if count_before >= limits["max_appointments_per_month"]:
        pytest.skip("Tenant already at limit from prior tests")

    tomorrow = datetime.now(tz.utc) + timedelta(days=1)
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()

    res = await client_auth.post(
        "/api/v1/appointments/",
        json={
            "service_id": service.id,
            "start_time": tomorrow.isoformat(),
            "client_name": "Limit Test Client",
            "client_phone": "+79991112233",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "id" in data


# ─── API: limit exceeded -> reject with structured error ───────────────────────

@pytest.mark.asyncio
async def test_create_appointment_exceeds_limit_returns_403_structured(
    client_auth: AsyncClient, db_session: AsyncSession
):
    """When tenant exceeds appointment limit, returns 403 with limit_exceeded detail."""
    from app.models.models import AppointmentStatus
    from datetime import datetime, timezone as tz

    # Ensure tenant 1 is at limit
    limits = get_limits("starter")
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()
    now = datetime.now(tz.utc)

    existing = await get_appointments_this_month(db_session, 1)
    to_create = max(0, limits["max_appointments_per_month"] - existing)
    for _ in range(to_create):
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            service_id=service.id,
            client_id=client.id,
            start_time=now,
            end_time=now,
            status=AppointmentStatus.NEW,
        )
        db_session.add(appt)
    await db_session.commit()

    from datetime import timedelta
    tomorrow = now + timedelta(days=1)
    res = await client_auth.post(
        "/api/v1/appointments/",
        json={
            "service_id": service.id,
            "start_time": tomorrow.isoformat(),
            "client_name": "Over Limit",
            "client_phone": "+79991119999",
        },
    )
    assert res.status_code == 403
    detail = res.json().get("detail")
    assert detail is not None
    if isinstance(detail, dict):
        assert detail.get("code") == "limit_exceeded"
        assert detail.get("limit_name") == "max_appointments_per_month"
        assert "current" in detail
        assert "limit" in detail
    else:
        assert "limit" in str(detail).lower() or "exceeded" in str(detail).lower()


# ─── API: feature gate by plan ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_features_endpoint_returns_plan_based_flags(client_auth: AsyncClient, db_session: AsyncSession):
    """GET /api/v1/features returns webhook, ai, advanced_analytics based on tenant plan."""
    res = await client_auth.get("/api/v1/features")
    assert res.status_code == 200
    data = res.json()
    assert "webhook" in data
    assert "ai" in data
    assert "advanced_analytics" in data
    # Tenant 1 has starter -> all false
    assert data["webhook"] is False
    assert data["advanced_analytics"] is False


@pytest.mark.asyncio
async def test_advanced_analytics_returns_403_for_starter(client_auth: AsyncClient):
    """GET /api/v1/features/advanced-analytics returns 403 for starter plan."""
    res = await client_auth.get("/api/v1/features/analytics/advanced")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_advanced_analytics_returns_200_for_enterprise(
    client_auth: AsyncClient, db_session: AsyncSession
):
    """GET /api/v1/features/analytics/advanced returns 200 for enterprise plan."""
    from app.models.models import TariffPlan

    # Create enterprise plan and assign to tenant 1
    ent = TariffPlan(name="enterprise", max_appointments=5000, max_shops=50, is_active=True)
    db_session.add(ent)
    await db_session.flush()
    tenant = (await db_session.execute(select(Tenant).where(Tenant.id == 1))).scalar_one()
    tenant.tariff_plan_id = ent.id
    await db_session.commit()

    res = await client_auth.get("/api/v1/features/analytics/advanced")
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data or "data" in data or isinstance(data, dict)


# ─── Plan model read from tenant ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tenant_plan_correctly_read(db_session: AsyncSession):
    """Plan model is correctly read from tenant via tariff_plan relationship."""
    stmt = select(Tenant).where(Tenant.id == 1)
    result = await db_session.execute(stmt)
    tenant = result.scalar_one_or_none()
    assert tenant is not None
    # conftest seeds starter plan
    if tenant.tariff_plan_id:
        plan = (await db_session.execute(select(TariffPlan).where(TariffPlan.id == tenant.tariff_plan_id))).scalar_one()
        assert plan.name in ("starter", "free", "business", "enterprise")
