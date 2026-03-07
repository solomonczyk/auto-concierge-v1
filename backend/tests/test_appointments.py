from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.api.endpoints import appointments as appointments_endpoint
from app.models.models import Appointment, AppointmentStatus, Client, Service, Shop


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
    """Kanban returns only waitlist/new/confirmed/in_progress/completed; excludes cancelled and no_show."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    c = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()
    base = datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc)

    kanban_statuses = (
        AppointmentStatus.WAITLIST,
        AppointmentStatus.NEW,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.COMPLETED,
    )
    excluded_statuses = (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW)

    for i, status in enumerate(kanban_statuses):
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            service_id=service.id,
            client_id=c.id,
            start_time=base + timedelta(hours=i),
            end_time=base + timedelta(hours=i, minutes=60),
            status=status,
        )
        db_session.add(appt)
    for i, status in enumerate(excluded_statuses):
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            service_id=service.id,
            client_id=c.id,
            start_time=base + timedelta(hours=10 + i),
            end_time=base + timedelta(hours=10 + i, minutes=60),
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

    statuses_in_response = [a["status"] for a in data]
    assert "cancelled" not in statuses_in_response
    assert "no_show" not in statuses_in_response

    for s in ("waitlist", "new", "confirmed", "in_progress", "completed"):
        assert s in statuses_in_response, f"Expected status '{s}' in kanban response"


@pytest.mark.asyncio
async def test_kanban_excludes_cancelled_and_no_show(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Kanban returns only waitlist/new/confirmed/in_progress/completed; excludes cancelled and no_show."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    base_time = datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc)
    kanban_statuses = [
        AppointmentStatus.WAITLIST,
        AppointmentStatus.NEW,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.COMPLETED,
    ]
    excluded_statuses = [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]

    for i, status in enumerate(kanban_statuses + excluded_statuses):
        start = base_time + timedelta(hours=i)
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            service_id=service.id,
            client_id=test_client.id,
            start_time=start,
            end_time=start + timedelta(minutes=60),
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
    for s in kanban_statuses:
        assert s.value in returned_statuses, f"Kanban status {s.value} must appear in response"
    assert "cancelled" not in returned_statuses and "no_show" not in returned_statuses, (
        "cancelled and no_show must not appear in kanban response"
    )


@pytest.mark.asyncio
async def test_kanban_includes_kanban_statuses_excludes_cancelled_no_show(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Kanban endpoint returns only waitlist/new/confirmed/in_progress/completed; excludes cancelled and no_show."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    base_time = datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc)
    kanban_statuses = [
        AppointmentStatus.WAITLIST,
        AppointmentStatus.NEW,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.COMPLETED,
    ]
    excluded_statuses = [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]

    for i, status in enumerate(kanban_statuses + excluded_statuses):
        appt = Appointment(
            tenant_id=1,
            shop_id=shop.id,
            service_id=service.id,
            client_id=test_client.id,
            start_time=base_time + timedelta(hours=i),
            end_time=base_time + timedelta(hours=i, minutes=60),
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
    assert all(s in ("waitlist", "new", "confirmed", "in_progress", "completed") for s in returned_statuses)
    assert "cancelled" not in returned_statuses
    assert "no_show" not in returned_statuses


@pytest.mark.asyncio
async def test_kanban_includes_only_kanban_statuses_excludes_cancelled_no_show(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Kanban endpoint returns waitlist/new/confirmed/in_progress/completed; excludes cancelled and no_show."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    test_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    base_time = datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc)
    kanban_statuses = [
        AppointmentStatus.WAITLIST,
        AppointmentStatus.NEW,
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.IN_PROGRESS,
        AppointmentStatus.COMPLETED,
    ]
    excluded_statuses = [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]

    for i, status in enumerate(kanban_statuses + excluded_statuses):
        start = base_time + timedelta(hours=i)
        db_session.add(
            Appointment(
                tenant_id=1,
                shop_id=shop.id,
                client_id=test_client.id,
                service_id=service.id,
                start_time=start,
                end_time=start + timedelta(minutes=60),
                status=status,
            )
        )
    await db_session.commit()

    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    res = await client.get(f"{settings.API_V1_STR}/appointments/kanban")
    assert res.status_code == 200
    data = res.json()

    returned_statuses = {a["status"] for a in data}
    assert returned_statuses == {"waitlist", "new", "confirmed", "in_progress", "completed"}
    assert "cancelled" not in returned_statuses
    assert "no_show" not in returned_statuses


KANBAN_STATUSES = {"waitlist", "new", "confirmed", "in_progress", "completed"}
EXCLUDED_STATUSES = {"cancelled", "no_show"}


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
    for i, status in enumerate(
        [
            AppointmentStatus.WAITLIST,
            AppointmentStatus.NEW,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.IN_PROGRESS,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        ]
    ):
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

    statuses_in_response = {item["status"] for item in data}
    for s in KANBAN_STATUSES:
        assert s in statuses_in_response or any(
            a["status"] == s for a in data
        ), f"Expected at least one {s} in kanban response"
    assert not statuses_in_response.intersection(
        EXCLUDED_STATUSES
    ), f"cancelled and no_show must not appear in kanban response, got: {statuses_in_response}"
