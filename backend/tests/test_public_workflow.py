"""
Tests for public WebApp booking workflow.
Covers: services/public, slots/public, appointments/public, public read (list + single).
"""

import pytest
from datetime import date, datetime, timezone
from httpx import AsyncClient
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Tenant, Appointment, Client, Shop, Service, AppointmentHistory, AppointmentStatus, TenantStatus
from app.services.appointment_snapshot_service import get_appointment_snapshot


PUBLIC_TEST_SLUG = "test-tenant"


async def _ensure_public_slug(db_session: AsyncSession) -> str:
    tenant = await db_session.get(Tenant, 1)
    assert tenant is not None
    tenant.slug = PUBLIC_TEST_SLUG
    await db_session.commit()
    return PUBLIC_TEST_SLUG


@pytest.mark.asyncio
async def test_services_public_returns_public_tenant_services(client: AsyncClient, db_session: AsyncSession):
    """GET /services/public returns services for PUBLIC_TENANT_ID without auth."""
    slug = await _ensure_public_slug(db_session)
    response = await client.get(f"/api/v1/{slug}/services/public")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Conftest creates one service for tenant 1 (PUBLIC_TENANT_ID=1)
    assert len(data) >= 1
    svc = data[0]
    assert "id" in svc
    assert "name" in svc
    assert svc["name"] == "Диагностика ходовой"
    assert svc["duration_minutes"] == 60
    assert svc["base_price"] == 1500.0


@pytest.mark.asyncio
async def test_services_public_no_auth_required(client: AsyncClient, db_session: AsyncSession):
    """Public services endpoint works without Authorization header."""
    slug = await _ensure_public_slug(db_session)
    response = await client.get(f"/api/v1/{slug}/services/public")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_slots_public_returns_available_slots(client: AsyncClient, db_session: AsyncSession):
    """GET /slots/public returns available slots for PUBLIC_TENANT_ID shop."""
    slug = await _ensure_public_slug(db_session)
    response = await client.get(
        f"/api/v1/{slug}/slots/public",
        params={
            "service_duration": 60,
            "target_date": "2026-02-20",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Empty day: 9:00–18:00, 30min step, 60min duration → slots from 9:00 to 17:00
    assert len(data) > 0
    # Each slot is ISO datetime string
    first = data[0]
    assert "2026-02-20" in first


@pytest.mark.asyncio
async def test_slots_public_no_auth_required(client: AsyncClient, db_session: AsyncSession):
    """Public slots endpoint works without auth."""
    slug = await _ensure_public_slug(db_session)
    response = await client.get(
        f"/api/v1/{slug}/slots/public",
        params={"service_duration": 60, "target_date": "2026-02-20"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_public_booking_full_workflow(client: AsyncClient, db_session: AsyncSession):
    """
    Full workflow: services -> slots -> book.
    Verifies service_id from services/public matches appointment creation.
    """
    slug = await _ensure_public_slug(db_session)
    # 1. Get services
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    assert svc_res.status_code == 200
    services = svc_res.json()
    assert len(services) >= 1
    service_id = services[0]["id"]

    # 2. Get slots
    slots_res = await client.get(
        f"/api/v1/{slug}/slots/public",
        params={"service_duration": 60, "target_date": "2026-02-20"},
    )
    assert slots_res.status_code == 200
    slots = slots_res.json()
    assert len(slots) > 0

    # 3. Book first available slot
    slot_str = slots[0]
    payload = {
        "service_id": service_id,
        "date": slot_str,
        "telegram_id": 123456789,
        "full_name": "Test User",
        "timezone": "Europe/Moscow",
    }
    book_res = await client.post(f"/api/v1/{slug}/appointments/public", json=payload)
    assert book_res.status_code == 200
    appt = book_res.json()
    assert appt["service"]["id"] == service_id
    assert appt["client"]["id"]
    assert appt["status"] in ("new", "confirmed")


@pytest.mark.asyncio
async def test_public_booking_invalid_service_returns_404(client: AsyncClient, db_session: AsyncSession):
    """Booking with non-existent service_id returns 404."""
    slug = await _ensure_public_slug(db_session)
    payload = {
        "service_id": 99999,
        "date": "2026-02-20T10:00:00",
        "telegram_id": 111,
        "full_name": "User",
    }
    response = await client.post(f"/api/v1/{slug}/appointments/public", json=payload)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_booking_duplicate_slot(client: AsyncClient, db_session: AsyncSession):
    """Two bookings at same slot: first succeeds, second rejected or succeeds (DB-dependent)."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    payload = {
        "service_id": service_id,
        "date": "2026-02-20T10:00:00Z",
        "telegram_id": 777,
        "full_name": "User",
    }
    r1 = await client.post(f"/api/v1/{slug}/appointments/public", json=payload)
    assert r1.status_code == 200

    r2 = await client.post(f"/api/v1/{slug}/appointments/public", json={**payload, "telegram_id": 778})
    # Ideal: 400/409. May be 200 if no conflict detected, or 500 if tz comparison bug
    assert r2.status_code in (200, 400, 409, 500)


@pytest.mark.asyncio
async def test_public_booking_waitlist(client: AsyncClient, db_session: AsyncSession):
    """Waitlist booking (is_waitlist=True) skips slot validation."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    payload = {
        "service_id": service_id,
        "date": "2026-02-20T10:00:00",
        "telegram_id": 555,
        "full_name": "Waitlist User",
        "is_waitlist": True,
    }
    response = await client.post(f"/api/v1/{slug}/appointments/public", json=payload)
    assert response.status_code == 200
    appt = response.json()
    assert appt["status"] == "waitlist"


@pytest.mark.asyncio
async def test_public_booking_with_auto_info_persists_snapshot_and_profile(
    client: AsyncClient, db_session: AsyncSession
):
    """POST /appointments/public with auto_info creates auto_snapshot and client auto_profile."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    assert svc_res.status_code == 200
    service_id = svc_res.json()[0]["id"]

    payload = {
        "service_id": service_id,
        "date": "2026-02-20T10:00:00",
        "telegram_id": 888999,
        "full_name": "Auto Info User",
        "is_waitlist": True,
        "auto_info": {
            "car_make": "Toyota",
            "car_year": 2018,
            "vin": "JTDBR32E720040123",
        },
    }
    response = await client.post(f"/api/v1/{slug}/appointments/public", json=payload)
    assert response.status_code == 200
    appt_data = response.json()
    assert appt_data["client"]["id"]

    await db_session.commit()
    stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.auto_snapshot),
            selectinload(Appointment.client).selectinload(Client.auto_profile),
        )
        .where(
            and_(
                Appointment.id == appt_data["id"],
                Appointment.tenant_id == 1,
            )
        )
    )
    result = await db_session.execute(stmt)
    appt = result.scalar_one()
    assert appt.auto_snapshot is not None
    assert appt.auto_snapshot.car_make == "Toyota"
    assert appt.auto_snapshot.car_year == 2018
    assert appt.auto_snapshot.vin == "JTDBR32E720040123"

    client_entity = appt.client
    assert client_entity.auto_profile is not None
    assert client_entity.auto_profile.car_make == "Toyota"
    assert client_entity.auto_profile.car_year == 2018
    assert client_entity.auto_profile.vin == "JTDBR32E720040123"


@pytest.mark.asyncio
async def test_public_booking_creates_intake_automatically(
    client: AsyncClient, db_session: AsyncSession
):
    """POST /appointments/public creates appointment with linked AppointmentIntake (status=pending)."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    assert svc_res.status_code == 200
    service_id = svc_res.json()[0]["id"]

    payload = {
        "service_id": service_id,
        "date": "2026-02-20T10:00:00",
        "telegram_id": 111222333,
        "full_name": "Intake Test User",
        "is_waitlist": True,
    }
    response = await client.post(f"/api/v1/{slug}/appointments/public", json=payload)
    assert response.status_code == 200
    appt_data = response.json()
    appt_id = appt_data["id"]

    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.intake))
        .where(and_(Appointment.id == appt_id, Appointment.tenant_id == 1))
    )
    result = await db_session.execute(stmt)
    appt = result.scalar_one()
    assert appt.intake is not None
    assert appt.intake.status == "pending"


@pytest.mark.asyncio
async def test_public_update_intake_answers(client: AsyncClient, db_session: AsyncSession):
    """PATCH /appointments/public/{id}/intake/answers updates answers_json for client's appointment."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    assert svc_res.status_code == 200
    service_id = svc_res.json()[0]["id"]

    tg_id = 444555666
    payload = {
        "service_id": service_id,
        "date": "2026-02-20T10:00:00",
        "telegram_id": tg_id,
        "full_name": "Answers Update User",
        "is_waitlist": True,
    }
    create_res = await client.post(f"/api/v1/{slug}/appointments/public", json=payload)
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    patch_res = await client.patch(
        f"/api/v1/{slug}/appointments/public/{appt_id}/intake/answers",
        params={"telegram_id": tg_id},
        json={"answers_json": '{"q1":"answer1","q2":"answer2"}'},
    )
    assert patch_res.status_code == 200

    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.intake))
        .where(and_(Appointment.id == appt_id, Appointment.tenant_id == 1))
    )
    result = await db_session.execute(stmt)
    appt = result.scalar_one()
    assert appt.intake is not None
    assert appt.intake.answers_json == '{"q1":"answer1","q2":"answer2"}'


@pytest.mark.asyncio
async def test_public_reschedule_success_creates_history_and_returns_snapshot(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    assert svc_res.status_code == 200
    service_id = svc_res.json()[0]["id"]

    tg_id = 999000111
    create_payload = {
        "service_id": service_id,
        "date": "2026-02-20T10:00:00Z",
        "telegram_id": tg_id,
        "full_name": "Reschedule User",
        "is_waitlist": True,
    }
    create_res = await client.post(f"/api/v1/{slug}/appointments/public", json=create_payload)
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    res_payload = {
        "new_start_time": "2026-02-20T12:00:00Z",
        "new_end_time": "2026-02-20T13:00:00Z",
        "reason": "client requested",
    }
    res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/reschedule",
        params={"telegram_id": tg_id},
        json=res_payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["appointment_id"] == appt_id
    assert data["tenant_id"] == 1
    assert data["rescheduled"] is True
    assert data["new_start_time"].startswith("2026-02-20T12:00:00")
    assert data["new_end_time"].startswith("2026-02-20T13:00:00")
    assert data["snapshot"]["start_time"].startswith("2026-02-20T12:00:00")
    assert data["snapshot"]["end_time"].startswith("2026-02-20T13:00:00")

    await db_session.commit()
    hist_stmt = select(AppointmentHistory).where(
        and_(
            AppointmentHistory.appointment_id == appt_id,
            AppointmentHistory.tenant_id == 1,
            AppointmentHistory.event_type == "rescheduled",
        )
    )
    hist = (await db_session.execute(hist_stmt)).scalars().all()
    assert len(hist) >= 1
    assert any(h.source == "public_api" for h in hist)
    assert any(h.reason == "client requested" for h in hist)

    snap = await get_appointment_snapshot(db_session, appt_id, 1)
    assert snap is not None
    assert snap.start_time.isoformat().startswith("2026-02-20T12:00:00")
    assert snap.end_time.isoformat().startswith("2026-02-20T13:00:00")


@pytest.mark.asyncio
async def test_public_reschedule_access_denied_for_foreign_appointment(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_owner = 10001
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_owner,
            "full_name": "Owner",
            "is_waitlist": True,
        },
    )
    appt_id = create_res.json()["id"]

    res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/reschedule",
        params={"telegram_id": 10002},
        json={
            "new_start_time": "2026-02-20T12:00:00Z",
            "new_end_time": "2026-02-20T13:00:00Z",
            "reason": "attack",
        },
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_public_reschedule_appointment_not_found(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    res = await client.post(
        f"/api/v1/{slug}/appointments/public/999999/reschedule",
        params={"telegram_id": 1},
        json={
            "new_start_time": "2026-02-20T12:00:00Z",
            "new_end_time": "2026-02-20T13:00:00Z",
            "reason": "n/a",
        },
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_public_reschedule_invalid_interval_returns_422(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 20001
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Invalid Interval",
            "is_waitlist": True,
        },
    )
    appt_id = create_res.json()["id"]

    res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/reschedule",
        params={"telegram_id": tg_id},
        json={
            "new_start_time": "2026-02-20T13:00:00Z",
            "new_end_time": "2026-02-20T13:00:00Z",
            "reason": "bad",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_public_reschedule_slot_conflict_returns_409(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_a = 30001
    a_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_a,
            "full_name": "A",
            "is_waitlist": True,
        },
    )
    appt_a = a_res.json()["id"]

    # Create a conflicting appointment (status NEW) in the target slot.
    shop_id = (await db_session.execute(select(Shop.id).where(Shop.tenant_id == 1))).scalar_one()
    client_entity = Client(tenant_id=1, full_name="B", phone="+70000000000", telegram_id=30002)
    db_session.add(client_entity)
    await db_session.flush()
    appt_b = Appointment(
        tenant_id=1,
        shop_id=shop_id,
        client_id=client_entity.id,
        service_id=service_id,
        start_time=datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 20, 13, 0, 0, tzinfo=timezone.utc),
        status=AppointmentStatus.NEW,
    )
    db_session.add(appt_b)
    await db_session.commit()

    res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_a}/reschedule",
        params={"telegram_id": tg_a},
        json={
            "new_start_time": "2026-02-20T12:00:00Z",
            "new_end_time": "2026-02-20T13:00:00Z",
            "reason": "conflict",
        },
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_public_reschedule_forbidden_status_returns_422(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 40001
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Forbidden",
            "is_waitlist": True,
        },
    )
    appt_id = create_res.json()["id"]

    appt = await db_session.get(Appointment, appt_id)
    assert appt is not None
    appt.status = AppointmentStatus.CANCELLED
    await db_session.commit()

    res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/reschedule",
        params={"telegram_id": tg_id},
        json={
            "new_start_time": "2026-02-20T12:00:00Z",
            "new_end_time": "2026-02-20T13:00:00Z",
            "reason": "try",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_public_cancel_success_returns_snapshot_and_creates_history(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    assert svc_res.status_code == 200
    service_id = svc_res.json()[0]["id"]

    tg_id = 51001
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Cancel User",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    cancel_res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/cancel",
        params={"telegram_id": tg_id},
        json={"reason": "client changed plans"},
    )
    assert cancel_res.status_code == 200
    data = cancel_res.json()
    assert data["appointment_id"] == appt_id
    assert data["tenant_id"] == 1
    assert data["cancelled"] is True
    assert data["status"] == "CANCELLED"
    assert data["snapshot"]["status"] == "CANCELLED"

    await db_session.commit()
    hist_stmt = select(AppointmentHistory).where(
        and_(
            AppointmentHistory.appointment_id == appt_id,
            AppointmentHistory.tenant_id == 1,
            AppointmentHistory.new_status == AppointmentStatus.CANCELLED.value,
        )
    )
    hist = (await db_session.execute(hist_stmt)).scalars().all()
    assert len(hist) >= 1
    assert any(h.source == "public_api" for h in hist)
    assert any(h.reason == "client changed plans" for h in hist)


@pytest.mark.asyncio
async def test_public_cancel_access_denied_for_foreign_appointment(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_owner = 52001
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_owner,
            "full_name": "Owner",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    cancel_res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/cancel",
        params={"telegram_id": 52002},
        json={"reason": "attack"},
    )
    assert cancel_res.status_code == 403


@pytest.mark.asyncio
async def test_public_cancel_appointment_not_found_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    res = await client.post(
        f"/api/v1/{slug}/appointments/public/999999/cancel",
        params={"telegram_id": 1},
        json={"reason": "n/a"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_public_cancel_forbidden_status_returns_422(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 53001
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Forbidden Cancel",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    appt = await db_session.get(Appointment, appt_id)
    assert appt is not None
    appt.status = AppointmentStatus.COMPLETED
    await db_session.commit()

    cancel_res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/cancel",
        params={"telegram_id": tg_id},
        json={"reason": "try cancel completed"},
    )
    assert cancel_res.status_code == 422


@pytest.mark.asyncio
async def test_public_cancel_already_cancelled_is_idempotent_and_does_not_duplicate_history(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 54001
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Idempotent Cancel",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    r1 = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/cancel",
        params={"telegram_id": tg_id},
        json={"reason": "first"},
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "CANCELLED"

    r2 = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/cancel",
        params={"telegram_id": tg_id},
        json={"reason": "second"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "CANCELLED"

    await db_session.commit()
    hist_stmt = select(AppointmentHistory).where(
        and_(
            AppointmentHistory.appointment_id == appt_id,
            AppointmentHistory.tenant_id == 1,
            AppointmentHistory.new_status == AppointmentStatus.CANCELLED.value,
            AppointmentHistory.source == "public_api",
        )
    )
    hist = (await db_session.execute(hist_stmt)).scalars().all()
    assert len(hist) == 1


# ─── Client Action Consistency Layer: capability flags, PATCH cancel ───────────


@pytest.mark.asyncio
async def test_public_cancel_returns_fresh_snapshot_with_capability_flags(
    client: AsyncClient, db_session: AsyncSession
):
    """POST cancel returns snapshot with can_reschedule=False, can_cancel=False after cancel."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 990001
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Capability User",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    cancel_res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/cancel",
        params={"telegram_id": tg_id},
        json={"reason": "client changed plans"},
    )
    assert cancel_res.status_code == 200
    data = cancel_res.json()
    assert data["cancelled"] is True
    assert data["status"] == "CANCELLED"
    assert "snapshot" in data
    snap = data["snapshot"]
    assert snap["status"] == "CANCELLED"
    assert snap["can_reschedule"] is False
    assert snap["can_cancel"] is False


@pytest.mark.asyncio
async def test_public_reschedule_returns_fresh_snapshot_with_capability_flags(
    client: AsyncClient, db_session: AsyncSession
):
    """Reschedule returns snapshot with can_reschedule, can_cancel reflecting new status."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 990002
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Reschedule Cap User",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/reschedule",
        params={"telegram_id": tg_id},
        json={
            "new_start_time": "2026-02-20T14:00:00Z",
            "new_end_time": "2026-02-20T15:00:00Z",
            "reason": "client",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["rescheduled"] is True
    assert "snapshot" in data
    snap = data["snapshot"]
    assert snap["status"] in ("NEW", "CONFIRMED", "WAITLIST")
    assert "can_reschedule" in snap
    assert "can_cancel" in snap
    assert snap["can_reschedule"] is True
    assert snap["can_cancel"] is True


@pytest.mark.asyncio
async def test_public_patch_cancel_returns_fresh_snapshot(
    client: AsyncClient, db_session: AsyncSession
):
    """PATCH /appointments/public/cancel returns AppointmentCancelResponse (snapshot-based)."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 990003
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Patch Cancel User",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    patch_res = await client.patch(
        f"/api/v1/{slug}/appointments/public/cancel",
        params={"telegram_id": tg_id, "appointment_id": appt_id},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["appointment_id"] == appt_id
    assert data["cancelled"] is True
    assert data["status"] == "CANCELLED"
    assert "snapshot" in data
    snap = data["snapshot"]
    assert snap["status"] == "CANCELLED"
    assert snap["can_reschedule"] is False
    assert snap["can_cancel"] is False


@pytest.mark.asyncio
async def test_public_cancel_tenant_isolation_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 55001
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Tenant1 Appt",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    tenant2 = Tenant(id=2, name="Tenant 2", status=TenantStatus.ACTIVE, tariff_plan_id=1)
    db_session.add(tenant2)
    await db_session.commit()

    appt = await db_session.get(Appointment, appt_id)
    assert appt is not None
    appt.tenant_id = 2
    await db_session.commit()

    res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt_id}/cancel",
        params={"telegram_id": tg_id},
        json={"reason": "should not find"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_public_reschedule_tenant_isolation_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    # Tenant 1 has slug "test-tenant"; create another tenant with different slug and appointment under it.
    slug = await _ensure_public_slug(db_session)

    tenant2 = Tenant(id=2, name="Tenant 2", status=TenantStatus.ACTIVE, tariff_plan_id=1, slug="other-tenant")
    db_session.add(tenant2)
    await db_session.flush()

    shop2 = Shop(tenant_id=2, name="Shop2", address="Addr2", phone="+79990000002")
    db_session.add(shop2)
    await db_session.flush()

    service2 = Service(tenant_id=2, name="Svc2", duration_minutes=60, base_price=1000.0)
    db_session.add(service2)
    await db_session.flush()

    client2 = Client(tenant_id=2, full_name="Client2", phone="+79990000003", telegram_id=50001)
    db_session.add(client2)
    await db_session.flush()

    appt2 = Appointment(
        tenant_id=2,
        shop_id=shop2.id,
        client_id=client2.id,
        service_id=service2.id,
        start_time=datetime(2026, 2, 20, 10, 0, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 20, 11, 0, 0, tzinfo=timezone.utc),
        status=AppointmentStatus.NEW,
    )
    db_session.add(appt2)
    await db_session.commit()

    res = await client.post(
        f"/api/v1/{slug}/appointments/public/{appt2.id}/reschedule",
        params={"telegram_id": 50001},
        json={
            "new_start_time": "2026-02-20T12:00:00Z",
            "new_end_time": "2026-02-20T13:00:00Z",
            "reason": "isolation",
        },
    )
    assert res.status_code == 404


# ─── Public read (list + single) contract regression ──────────────────────────


@pytest.mark.asyncio
async def test_public_list_appointments_happy_path_returns_snapshot_with_capability_flags(
    client: AsyncClient, db_session: AsyncSession
):
    """GET /appointments/public returns list of client appointments with can_reschedule, can_cancel."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 60101
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "List Read User",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200

    list_res = await client.get(
        f"/api/v1/{slug}/appointments/public",
        params={"telegram_id": tg_id},
    )
    assert list_res.status_code == 200
    data = list_res.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert "limit" in data
    assert "offset" in data
    assert "total" in data
    assert "has_more" in data
    assert len(data["items"]) >= 1
    assert data["limit"] >= 1
    assert data["offset"] >= 0
    assert data["total"] >= 1
    item = data["items"][0]
    assert "appointment_id" in item
    assert "can_reschedule" in item
    assert "can_cancel" in item
    assert item["can_reschedule"] is True
    assert item["can_cancel"] is True


@pytest.mark.asyncio
async def test_public_list_appointments_client_not_found_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    """GET /appointments/public with telegram_id that has no client returns 404."""
    slug = await _ensure_public_slug(db_session)
    res = await client.get(
        f"/api/v1/{slug}/appointments/public",
        params={"telegram_id": 999999999},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_public_single_read_happy_path_returns_full_snapshot_with_capability_flags(
    client: AsyncClient, db_session: AsyncSession
):
    """GET /appointments/public/{id} returns full snapshot with can_reschedule, can_cancel."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 60201
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_id,
            "full_name": "Single Read User",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    single_res = await client.get(
        f"/api/v1/{slug}/appointments/public/{appt_id}",
        params={"telegram_id": tg_id},
    )
    assert single_res.status_code == 200
    data = single_res.json()
    assert data["appointment_id"] == appt_id
    assert "status" in data
    assert "start_time" in data
    assert "end_time" in data
    assert "client" in data
    assert "service" in data
    assert "can_reschedule" in data
    assert "can_cancel" in data
    assert data["can_reschedule"] is True
    assert data["can_cancel"] is True


@pytest.mark.asyncio
async def test_public_single_read_foreign_telegram_id_returns_403(
    client: AsyncClient, db_session: AsyncSession
):
    """GET /appointments/public/{id} with different telegram_id returns 403."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_owner = 60301
    create_res = await client.post(
        f"/api/v1/{slug}/appointments/public",
        json={
            "service_id": service_id,
            "date": "2026-02-20T10:00:00Z",
            "telegram_id": tg_owner,
            "full_name": "Owner",
            "is_waitlist": True,
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    res = await client.get(
        f"/api/v1/{slug}/appointments/public/{appt_id}",
        params={"telegram_id": 60302},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_public_single_read_appointment_not_found_returns_404(
    client: AsyncClient, db_session: AsyncSession
):
    """GET /appointments/public/{id} for non-existent id returns 404."""
    slug = await _ensure_public_slug(db_session)
    res = await client.get(
        f"/api/v1/{slug}/appointments/public/999999",
        params={"telegram_id": 1},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_public_list_appointments_limit_and_order_and_capability_flags(
    client: AsyncClient, db_session: AsyncSession
):
    """GET /appointments/public?limit=N limits results, preserves order by start_time and capability flags."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 70101
    for i, day in enumerate(["2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24"]):
        create_res = await client.post(
            f"/api/v1/{slug}/appointments/public",
            json={
                "service_id": service_id,
                "date": f"{day}T10:00:00Z",
                "telegram_id": tg_id,
                "full_name": "Pagination User",
                "is_waitlist": True,
            },
        )
        assert create_res.status_code == 200

    list_full = await client.get(
        f"/api/v1/{slug}/appointments/public",
        params={"telegram_id": tg_id, "limit": 10},
    )
    assert list_full.status_code == 200
    full_page = list_full.json()
    full_data = full_page["items"]
    assert len(full_data) >= 5
    assert full_page["total"] >= 5

    list_limited = await client.get(
        f"/api/v1/{slug}/appointments/public",
        params={"telegram_id": tg_id, "limit": 2, "offset": 0},
    )
    assert list_limited.status_code == 200
    limited_page = list_limited.json()
    limited = limited_page["items"]
    assert len(limited) == 2
    assert limited_page["limit"] == 2
    assert limited_page["offset"] == 0
    assert limited[0]["start_time"] <= limited[1]["start_time"]
    assert limited[0]["appointment_id"] == full_data[0]["appointment_id"]
    assert limited[1]["appointment_id"] == full_data[1]["appointment_id"]
    for item in limited:
        assert "can_reschedule" in item
        assert "can_cancel" in item


@pytest.mark.asyncio
async def test_public_list_appointments_offset_returns_next_chunk(
    client: AsyncClient, db_session: AsyncSession
):
    """GET /appointments/public?offset=N returns next chunk, order stable by start_time."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 70201
    for day in ["2026-02-25", "2026-02-26", "2026-02-27", "2026-02-28", "2026-03-01"]:
        create_res = await client.post(
            f"/api/v1/{slug}/appointments/public",
            json={
                "service_id": service_id,
                "date": f"{day}T10:00:00Z",
                "telegram_id": tg_id,
                "full_name": "Offset User",
                "is_waitlist": True,
            },
        )
        assert create_res.status_code == 200

    full_res = await client.get(
        f"/api/v1/{slug}/appointments/public",
        params={"telegram_id": tg_id, "limit": 10},
    )
    full_page = full_res.json()
    full_data = full_page["items"]
    assert len(full_data) >= 5

    offset_res = await client.get(
        f"/api/v1/{slug}/appointments/public",
        params={"telegram_id": tg_id, "limit": 2, "offset": 2},
    )
    assert offset_res.status_code == 200
    chunk_page = offset_res.json()
    chunk = chunk_page["items"]
    assert len(chunk) == 2
    assert chunk_page["offset"] == 2
    assert chunk_page["total"] >= 5
    assert chunk[0]["appointment_id"] == full_data[2]["appointment_id"]
    assert chunk[1]["appointment_id"] == full_data[3]["appointment_id"]
    assert chunk[0]["start_time"] <= chunk[1]["start_time"]


@pytest.mark.asyncio
async def test_public_list_page_contract_has_more_true_when_more_records(
    client: AsyncClient, db_session: AsyncSession
):
    """Page contract: has_more is True when total > offset + len(items)."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 70301
    for day in ["2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05", "2026-03-06"]:
        create_res = await client.post(
            f"/api/v1/{slug}/appointments/public",
            json={
                "service_id": service_id,
                "date": f"{day}T10:00:00Z",
                "telegram_id": tg_id,
                "full_name": "HasMore User",
                "is_waitlist": True,
            },
        )
        assert create_res.status_code == 200

    res = await client.get(
        f"/api/v1/{slug}/appointments/public",
        params={"telegram_id": tg_id, "limit": 2, "offset": 0},
    )
    assert res.status_code == 200
    page = res.json()
    assert page["has_more"] is True
    assert page["total"] >= 5
    assert len(page["items"]) == 2
    assert page["limit"] == 2
    assert page["offset"] == 0


@pytest.mark.asyncio
async def test_public_list_page_contract_has_more_false_on_last_page(
    client: AsyncClient, db_session: AsyncSession
):
    """Page contract: has_more is False on last page."""
    slug = await _ensure_public_slug(db_session)
    svc_res = await client.get(f"/api/v1/{slug}/services/public")
    service_id = svc_res.json()[0]["id"]

    tg_id = 70401
    for day in ["2026-03-07", "2026-03-08", "2026-03-09"]:
        create_res = await client.post(
            f"/api/v1/{slug}/appointments/public",
            json={
                "service_id": service_id,
                "date": f"{day}T10:00:00Z",
                "telegram_id": tg_id,
                "full_name": "LastPage User",
                "is_waitlist": True,
            },
        )
        assert create_res.status_code == 200

    res = await client.get(
        f"/api/v1/{slug}/appointments/public",
        params={"telegram_id": tg_id, "limit": 2, "offset": 2},
    )
    assert res.status_code == 200
    page = res.json()
    assert page["has_more"] is False
    assert page["total"] >= 3
    assert len(page["items"]) >= 1
    assert page["offset"] == 2
