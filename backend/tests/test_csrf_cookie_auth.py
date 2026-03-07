"""
CSRF protection via double-submit cookie — tests.

- GET /me: works without CSRF (read-only).
- Mutating (POST, PATCH, PUT, DELETE) with auth cookie: require X-CSRF-Token header.
- Without CSRF header → 403.
- With valid CSRF header (matches cookie) → 200/204.
"""
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Appointment, AppointmentStatus, Client, Service, Shop


async def _login(client: AsyncClient) -> str | None:
    """Login, set auth + CSRF cookies. Returns csrf_token for header."""
    res = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    assert "access_token" in res.cookies or client.cookies.get("access_token")
    csrf = res.cookies.get("csrf_token") or client.cookies.get("csrf_token")
    return csrf


def _csrf_headers(csrf_token: str) -> dict:
    return {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_get_me_works_without_csrf(client: AsyncClient):
    """GET /me (read-only) works with auth cookie, no CSRF header required."""
    await _login(client)
    res = await client.get(f"{settings.API_V1_STR}/me")
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "admin"


@pytest.mark.asyncio
async def test_mutating_without_csrf_header_rejected(client: AsyncClient):
    """POST /auth/logout without X-CSRF-Token → 403."""
    await _login(client)
    res = await client.post(f"{settings.API_V1_STR}/auth/logout")
    assert res.status_code == 403
    assert "csrf" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_mutating_with_csrf_header_succeeds_logout(client: AsyncClient):
    """POST /auth/logout with valid X-CSRF-Token → 200."""
    csrf = await _login(client)
    assert csrf
    res = await client.post(
        f"{settings.API_V1_STR}/auth/logout",
        headers=_csrf_headers(csrf),
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_mutating_with_csrf_header_succeeds_create_appointment(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """POST /appointments/ with valid X-CSRF-Token → 200."""
    csrf = await _login(client)
    assert csrf
    appt_data = {
        "service_id": 1,
        "start_time": "2026-03-15T14:00:00",
        "client_name": "CSRF Test Client",
        "client_phone": "+79991112233",
    }
    res = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
        headers=_csrf_headers(csrf),
    )
    assert res.status_code == 200
    assert res.json().get("id")


@pytest.mark.asyncio
async def test_mutating_with_csrf_header_succeeds_patch_status(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """PATCH /appointments/{id}/status with valid X-CSRF-Token → 200."""
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    client_orm = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    start = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=service.duration_minutes)
    appt = Appointment(
        tenant_id=1,
        shop_id=shop.id,
        service_id=service.id,
        client_id=client_orm.id,
        start_time=start,
        end_time=end,
        status=AppointmentStatus.NEW,
    )
    db_session.add(appt)
    await db_session.commit()
    await db_session.refresh(appt)
    appt_id = appt.id

    csrf = await _login(client)
    assert csrf
    res = await client.patch(
        f"{settings.API_V1_STR}/appointments/{appt_id}/status",
        json={"status": "confirmed"},
        headers=_csrf_headers(csrf),
    )
    assert res.status_code == 200
    assert res.json().get("status") == "confirmed"
