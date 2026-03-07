import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.api.endpoints import appointments as appointments_endpoint
from app.models.models import Appointment, AppointmentHistory, AppointmentStatus, Client, Service, Shop


@pytest.mark.asyncio
async def test_create_appointment_unauthorized(client: AsyncClient):
    appt_data = {
        "shop_id": 1,
        "service_id": 1,
        "start_time": "2026-02-20T10:00:00",
        "client_name": "Test User",
        "client_phone": "+1234567890",
    }
    response = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_appointment_authorized(client: AsyncClient):
    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    appt_data = {
        "service_id": 1,
        "start_time": "2026-02-20T12:00:00",
        "client_name": "Authorized User",
        "client_phone": "+0987654321",
    }
    response = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"]
    assert data["shop_id"] == 1


@pytest.mark.asyncio
async def test_create_appointment_survives_external_integration_failure(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Regression: integration failure must not break appointment creation API."""
    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    def broken_enqueue(_appointment_id: int, _tenant_id: int) -> bool:
        raise RuntimeError("integration queue down")

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "enqueue_appointment",
        broken_enqueue,
    )

    appt_data = {
        "service_id": 1,
        "start_time": "2026-02-20T13:00:00",
        "client_name": "Integration Failure Safe",
        "client_phone": "+70000000001",
    }
    create_res = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
    )

    assert create_res.status_code == 200
    created = create_res.json()
    assert created["id"] > 0
    assert created["client_id"] > 0
    assert created["service_id"] == 1

    list_res = await client.get(f"{settings.API_V1_STR}/appointments/")
    assert list_res.status_code == 200
    ids = {item["id"] for item in list_res.json()}
    assert created["id"] in ids


@pytest.mark.asyncio
async def test_kanban_excludes_cancelled_and_no_show(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Kanban endpoint returns only waitlist/new/confirmed/in_progress/completed.
    cancelled and no_show must not appear in response.
    """
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    base_time = datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc)
    kanban_statuses = (
        AppointmentStatus.WAITLIST,
        AppointmentStatus.NEW,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.COMPLETED,
    )
    excluded_statuses = (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW)

    for i, status in enumerate(kanban_statuses + excluded_statuses):
        start = base_time + timedelta(hours=i)
        end = start + timedelta(minutes=service.duration_minutes)
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            client_id=test_client.id,
            service_id=service.id,
            start_time=start,
            end_time=end,
            status=status,
        )
        db_session.add(appt)
    await db_session.commit()

    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    res = await client.get(f"{settings.API_V1_STR}/appointments/kanban")
    assert res.status_code == 200
    data = res.json()

    returned_statuses = [a["status"] for a in data]
    for s in ("waitlist", "new", "confirmed", "in_progress", "completed"):
        assert s in returned_statuses, f"Kanban must include status {s}"

    assert "cancelled" not in returned_statuses, "cancelled must not appear in kanban response"
    assert "no_show" not in returned_statuses, "no_show must not appear in kanban response"


@pytest.mark.asyncio
async def test_terminal_includes_only_cancelled_and_no_show(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Terminal endpoint returns only cancelled and no_show.
    waitlist/new/confirmed/in_progress/completed must not appear.
    """
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    base_time = datetime(2026, 3, 11, 10, 0, 0, tzinfo=timezone.utc)
    terminal_statuses = (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW)
    non_terminal_statuses = (
        AppointmentStatus.WAITLIST,
        AppointmentStatus.NEW,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.COMPLETED,
    )

    for i, status in enumerate(terminal_statuses + non_terminal_statuses):
        start = base_time + timedelta(hours=i)
        end = start + timedelta(minutes=service.duration_minutes)
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            client_id=test_client.id,
            service_id=service.id,
            start_time=start,
            end_time=end,
            status=status,
        )
        db_session.add(appt)
    await db_session.commit()

    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    res = await client.get(f"{settings.API_V1_STR}/appointments/terminal")
    assert res.status_code == 200
    data = res.json()

    returned_statuses = [a["status"] for a in data]
    assert "cancelled" in returned_statuses, "terminal must include cancelled"
    assert "no_show" in returned_statuses, "terminal must include no_show"
    for s in ("waitlist", "new", "confirmed", "in_progress", "completed"):
        assert s not in returned_statuses, f"terminal must not include status {s}"


@pytest.mark.asyncio
async def test_terminal_limit_validation(client: AsyncClient):
    """limit must be 1..100: limit=0 and limit=101 return 422, limit=100 returns 200."""
    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    res_0 = await client.get(f"{settings.API_V1_STR}/appointments/terminal?limit=0")
    assert res_0.status_code == 422, f"limit=0: expected 422, got {res_0.status_code}, body={res_0.json()}"

    res_101 = await client.get(f"{settings.API_V1_STR}/appointments/terminal?limit=101")
    assert res_101.status_code == 422, f"limit=101: expected 422, got {res_101.status_code}, body={res_101.json()}"

    res_100 = await client.get(f"{settings.API_V1_STR}/appointments/terminal?limit=100")
    assert res_100.status_code == 200, f"limit=100: expected 200, got {res_100.status_code}, body={res_100.json()}"
    assert isinstance(res_100.json(), list)


@pytest.mark.asyncio
async def test_terminal_orders_by_created_at_desc(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Terminal endpoint returns records ordered by created_at DESC (newest first)."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    base = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)
    for i, status in enumerate([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW, AppointmentStatus.CANCELLED]):
        created = base - timedelta(hours=i)
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            client_id=test_client.id,
            service_id=service.id,
            start_time=base + timedelta(hours=i),
            end_time=base + timedelta(hours=i, minutes=service.duration_minutes),
            status=status,
            created_at=created,
        )
        db_session.add(appt)
    await db_session.commit()

    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    res = await client.get(f"{settings.API_V1_STR}/appointments/terminal")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 3
    created_ats = [datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")) for a in data[:3]]
    assert created_ats == sorted(created_ats, reverse=True), "terminal must return newest first (created_at DESC)"


@pytest.mark.asyncio
async def test_terminal_pagination_skip_returns_second_record(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """skip=1&limit=1 returns the second record (by created_at DESC)."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    base = datetime(2026, 3, 13, 10, 0, 0, tzinfo=timezone.utc)
    ids_in_order = []
    for i in range(3):
        created = base - timedelta(hours=i)
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            client_id=test_client.id,
            service_id=service.id,
            start_time=base + timedelta(hours=i),
            end_time=base + timedelta(hours=i, minutes=service.duration_minutes),
            status=AppointmentStatus.CANCELLED,
            created_at=created,
        )
        db_session.add(appt)
        await db_session.flush()
        ids_in_order.append(appt.id)
    await db_session.commit()

    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    res = await client.get(f"{settings.API_V1_STR}/appointments/terminal?skip=1&limit=1")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == ids_in_order[1], "skip=1&limit=1 must return second record (created_at DESC)"


@pytest.mark.asyncio
async def test_terminal_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Terminal endpoint does not return appointments from another tenant."""
    from app.models.models import Tenant, TariffPlan
    from sqlalchemy import select as sql_select

    tariff = (await db_session.execute(sql_select(TariffPlan).limit(1))).scalar_one()
    shop1 = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service1 = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    client1 = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    tenant_b = Tenant(
        id=2,
        name="Tenant B",
        status="active",
        tariff_plan_id=tariff.id,
        slug="tenant-b",
    )
    db_session.add(tenant_b)
    await db_session.flush()

    shop_b = Shop(tenant_id=2, name="Shop B", address="Addr B", phone="+79990000002")
    db_session.add(shop_b)
    await db_session.flush()
    service_b = Service(tenant_id=2, name="Svc B", duration_minutes=30, base_price=500.0)
    db_session.add(service_b)
    await db_session.flush()
    client_b = Client(tenant_id=2, full_name="Client B", phone="+79990000003")
    db_session.add(client_b)
    await db_session.flush()

    appt_tenant_b = Appointment(
        tenant_id=2,
        shop_id=shop_b.id,
        client_id=client_b.id,
        service_id=service_b.id,
        start_time=datetime(2026, 3, 14, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 14, 10, 30, 0, tzinfo=timezone.utc),
        status=AppointmentStatus.CANCELLED,
    )
    db_session.add(appt_tenant_b)
    await db_session.flush()
    other_tenant_appt_id = appt_tenant_b.id

    appt_tenant_a = Appointment(
        tenant_id=1,
        shop_id=shop1.id,
        client_id=client1.id,
        service_id=service1.id,
        start_time=datetime(2026, 3, 14, 11, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 14, 11, 30, 0, tzinfo=timezone.utc),
        status=AppointmentStatus.NO_SHOW,
    )
    db_session.add(appt_tenant_a)
    await db_session.commit()

    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    res = await client.get(f"{settings.API_V1_STR}/appointments/terminal")
    assert res.status_code == 200
    data = res.json()
    returned_ids = [a["id"] for a in data]
    assert other_tenant_appt_id not in returned_ids, "tenant A must not see tenant B appointments"


# ─── Today appointments endpoint ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_today_only_today_records(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Today endpoint: today in, yesterday and tomorrow out."""
    from app.models.models import TenantSettings

    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    tz_name = settings.SHOP_TIMEZONE
    tz_obj = ZoneInfo(tz_name)
    fixed_now = datetime(2026, 3, 25, 12, 0, 0, tzinfo=tz_obj)
    day_start = fixed_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_10 = (day_start + timedelta(hours=10)).astimezone(timezone.utc)
    yesterday_10 = (day_start - timedelta(days=1) + timedelta(hours=10)).astimezone(timezone.utc)
    tomorrow_10 = (day_start + timedelta(days=1) + timedelta(hours=10)).astimezone(timezone.utc)

    def make_appt(st, et):
        return Appointment(
            tenant_id=1,
            shop_id=shop.id,
            client_id=test_client.id,
            service_id=service.id,
            start_time=st,
            end_time=et,
            status=AppointmentStatus.NEW,
        )

    db_session.add(make_appt(yesterday_10, yesterday_10 + timedelta(minutes=service.duration_minutes)))
    db_session.add(make_appt(today_10, today_10 + timedelta(minutes=service.duration_minutes)))
    db_session.add(make_appt(tomorrow_10, tomorrow_10 + timedelta(minutes=service.duration_minutes)))
    await db_session.commit()

    with patch("app.api.endpoints.appointments.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_now
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a or k else fixed_now
        await client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        res = await client.get(f"{settings.API_V1_STR}/appointments/today")
    assert res.status_code == 200
    data = res.json()
    ids = [a["id"] for a in data]
    start_times = [a["start_time"] for a in data]
    assert any(today_10.isoformat() in st or st.startswith("2026-03-25") for st in start_times), "today record must be in response"
    assert not any("2026-03-24" in st for st in start_times), "yesterday must not appear"
    assert not any("2026-03-26" in st for st in start_times), "tomorrow must not appear"
    assert len(data) == 1


@pytest.mark.asyncio
async def test_today_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Today endpoint does not return tenant B appointments."""
    from app.models.models import Tenant, TariffPlan

    tz_obj = ZoneInfo(settings.SHOP_TIMEZONE)
    day_start = datetime(2026, 3, 26, 0, 0, 0, tzinfo=tz_obj)
    today_10 = (day_start + timedelta(hours=10)).astimezone(timezone.utc)

    tariff = (await db_session.execute(select(TariffPlan).limit(1))).scalar_one()
    shop1 = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service1 = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    client1 = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    tenant_b = Tenant(id=2, name="Tenant B", status="active", tariff_plan_id=tariff.id, slug="tenant-b")
    db_session.add(tenant_b)
    await db_session.flush()
    shop_b = Shop(tenant_id=2, name="Shop B", address="Addr B", phone="+79990000002")
    db_session.add(shop_b)
    await db_session.flush()
    service_b = Service(tenant_id=2, name="Svc B", duration_minutes=30, base_price=500.0)
    db_session.add(service_b)
    await db_session.flush()
    client_b = Client(tenant_id=2, full_name="Client B", phone="+79990000003")
    db_session.add(client_b)
    await db_session.flush()

    appt_b = Appointment(
        tenant_id=2,
        shop_id=shop_b.id,
        client_id=client_b.id,
        service_id=service_b.id,
        start_time=today_10,
        end_time=today_10 + timedelta(minutes=30),
        status=AppointmentStatus.NEW,
    )
    db_session.add(appt_b)
    await db_session.flush()
    other_tenant_appt_id = appt_b.id

    appt_a = Appointment(
        tenant_id=1,
        shop_id=shop1.id,
        client_id=client1.id,
        service_id=service1.id,
        start_time=today_10,
        end_time=today_10 + timedelta(minutes=30),
        status=AppointmentStatus.NEW,
    )
    db_session.add(appt_a)
    await db_session.commit()

    with patch("app.api.endpoints.appointments.datetime") as mock_dt:
        mock_dt.now.return_value = day_start + timedelta(hours=12)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a or k else (day_start + timedelta(hours=12))
        await client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        res = await client.get(f"{settings.API_V1_STR}/appointments/today")
    assert res.status_code == 200
    data = res.json()
    returned_ids = [a["id"] for a in data]
    assert other_tenant_appt_id not in returned_ids, "tenant A must not see tenant B today appointments"


@pytest.mark.asyncio
async def test_today_sorted_by_start_time_asc(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Today endpoint returns records ordered by start_time ASC."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    tz_obj = ZoneInfo(settings.SHOP_TIMEZONE)
    day_start = datetime(2026, 3, 27, 0, 0, 0, tzinfo=tz_obj)
    for h in [12, 10, 14]:
        st = (day_start + timedelta(hours=h)).astimezone(timezone.utc)
        et = st + timedelta(minutes=service.duration_minutes)
        db_session.add(Appointment(
            tenant_id=1,
            shop_id=shop.id,
            client_id=test_client.id,
            service_id=service.id,
            start_time=st,
            end_time=et,
            status=AppointmentStatus.NEW,
        ))
    await db_session.commit()

    with patch("app.api.endpoints.appointments.datetime") as mock_dt:
        mock_dt.now.return_value = day_start + timedelta(hours=8)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a or k else (day_start + timedelta(hours=8))
        await client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        res = await client.get(f"{settings.API_V1_STR}/appointments/today")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 3
    start_times = [a["start_time"] for a in data[:3]]
    assert start_times == sorted(start_times), "today must be sorted by start_time ASC"


@pytest.mark.asyncio
async def test_today_limit_validation(client: AsyncClient):
    """limit 1..100: limit=0 and limit=101 return 422, limit=100 returns 200."""
    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    res_0 = await client.get(f"{settings.API_V1_STR}/appointments/today?limit=0")
    assert res_0.status_code == 422
    res_101 = await client.get(f"{settings.API_V1_STR}/appointments/today?limit=101")
    assert res_101.status_code == 422
    res_100 = await client.get(f"{settings.API_V1_STR}/appointments/today?limit=100")
    assert res_100.status_code == 200
    assert isinstance(res_100.json(), list)


@pytest.mark.asyncio
async def test_today_skip_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """skip=1&limit=1 returns second record by start_time ASC."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    tz_obj = ZoneInfo(settings.SHOP_TIMEZONE)
    day_start = datetime(2026, 3, 28, 0, 0, 0, tzinfo=tz_obj)
    ids_in_order = []
    for h in [9, 10, 11]:
        st = (day_start + timedelta(hours=h)).astimezone(timezone.utc)
        et = st + timedelta(minutes=service.duration_minutes)
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            client_id=test_client.id,
            service_id=service.id,
            start_time=st,
            end_time=et,
            status=AppointmentStatus.NEW,
        )
        db_session.add(appt)
        await db_session.flush()
        ids_in_order.append(appt.id)
    await db_session.commit()

    with patch("app.api.endpoints.appointments.datetime") as mock_dt:
        mock_dt.now.return_value = day_start + timedelta(hours=8)
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k) if a or k else (day_start + timedelta(hours=8))
        await client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        res = await client.get(f"{settings.API_V1_STR}/appointments/today?skip=1&limit=1")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == ids_in_order[1], "skip=1&limit=1 must return second record"


@pytest.mark.asyncio
async def test_appointment_history_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """
    GET /appointments/{id}/history: sorting ASC, actor, tenant isolation, empty history.
    """
    from app.models.models import Tenant, TariffPlan

    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    create_res = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": "2026-03-20T10:00:00",
            "client_name": "History Test Client",
            "client_phone": "+79991113344",
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    patch_res = await client.patch(
        f"{settings.API_V1_STR}/appointments/{appt_id}/status",
        json={"status": "confirmed"},
    )
    assert patch_res.status_code == 200

    res = await client.get(f"{settings.API_V1_STR}/appointments/{appt_id}/history")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    created_ats = [h["created_at"] for h in data]
    assert created_ats == sorted(created_ats), "history must be sorted by created_at ASC"

    first_with_actor = next((h for h in data if h.get("actor")), None)
    assert first_with_actor is not None, "at least one record must have actor"
    assert first_with_actor["actor"] == "admin", "actor must be admin when changed by user"


@pytest.mark.asyncio
async def test_appointment_history_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """History endpoint must not return records from another tenant."""
    from app.models.models import Tenant, TariffPlan

    tariff = (await db_session.execute(select(TariffPlan).limit(1))).scalar_one()
    shop1 = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service1 = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    client1 = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    tenant_b = Tenant(id=2, name="Tenant B", status="active", tariff_plan_id=tariff.id, slug="tenant-b")
    db_session.add(tenant_b)
    await db_session.flush()
    shop_b = Shop(tenant_id=2, name="Shop B", address="Addr B", phone="+79990000002")
    db_session.add(shop_b)
    await db_session.flush()
    service_b = Service(tenant_id=2, name="Svc B", duration_minutes=30, base_price=500.0)
    db_session.add(service_b)
    await db_session.flush()
    client_b = Client(tenant_id=2, full_name="Client B", phone="+79990000003")
    db_session.add(client_b)
    await db_session.flush()

    appt_b = Appointment(
        tenant_id=2,
        shop_id=shop_b.id,
        client_id=client_b.id,
        service_id=service_b.id,
        start_time=datetime(2026, 3, 21, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 21, 10, 30, 0, tzinfo=timezone.utc),
        status=AppointmentStatus.CANCELLED,
    )
    db_session.add(appt_b)
    await db_session.flush()
    hist_b = AppointmentHistory(
        appointment_id=appt_b.id,
        tenant_id=2,
        old_status="new",
        new_status="cancelled",
        source="api",
    )
    db_session.add(hist_b)
    await db_session.flush()
    other_tenant_history_id = hist_b.id

    appt_a = Appointment(
        tenant_id=1,
        shop_id=shop1.id,
        client_id=client1.id,
        service_id=service1.id,
        start_time=datetime(2026, 3, 21, 11, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 21, 11, 30, 0, tzinfo=timezone.utc),
        status=AppointmentStatus.NEW,
    )
    db_session.add(appt_a)
    await db_session.commit()

    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    res = await client.get(f"{settings.API_V1_STR}/appointments/{appt_a.id}/history")
    assert res.status_code == 200
    data = res.json()
    returned_ids = [h["id"] for h in data]
    assert other_tenant_history_id not in returned_ids, "tenant A must not see tenant B history"


@pytest.mark.asyncio
async def test_appointment_history_empty_returns_200_and_empty_list(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Appointment with no history returns 200 and []."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    appt = Appointment(
        tenant_id=1,
        shop_id=shop.id,
        client_id=test_client.id,
        service_id=service.id,
        start_time=datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 3, 22, 10, 30, 0, tzinfo=timezone.utc),
        status=AppointmentStatus.NEW,
    )
    db_session.add(appt)
    await db_session.commit()

    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    res = await client.get(f"{settings.API_V1_STR}/appointments/{appt.id}/history")
    assert res.status_code == 200
    data = res.json()
    assert data == [], "empty history must return []"


@pytest.mark.asyncio
async def test_patch_status_publishes_appointment_status_updated(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """PATCH /appointments/{id}/status publishes appointment_status_updated to Redis for Kanban WS."""
    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    create_res = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": "2026-03-15T10:00:00",
            "client_name": "Status Test Client",
            "client_phone": "+79991112233",
        },
    )
    assert create_res.status_code == 200
    appt = create_res.json()
    appt_id = appt["id"]
    tenant_id = 1

    mock_redis = MagicMock()
    mock_redis.publish = AsyncMock(return_value=1)
    with patch("app.api.endpoints.appointments.RedisService") as mock_svc:
        mock_svc.get_redis.return_value = mock_redis
        res = await client.patch(
            f"{settings.API_V1_STR}/appointments/{appt_id}/status",
            json={"status": "confirmed"},
        )

    assert res.status_code == 200
    mock_redis.publish.assert_called()
    channel = mock_redis.publish.call_args[0][0]
    payload_str = mock_redis.publish.call_args[0][1]

    assert channel == f"appointments_updates:{tenant_id}"

    payload = json.loads(payload_str)
    assert payload["type"] == "appointment_status_updated"
    assert payload["appointment_id"] == appt_id
    assert payload["old_status"] == "new"
    assert payload["new_status"] == "confirmed"
