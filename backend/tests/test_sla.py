"""Tests for SLA alerts API."""

from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Appointment, AppointmentStatus, Client, Service, Shop


@pytest.mark.asyncio
async def test_sla_unconfirmed_returns_only_overdue_new_appointments(
    client_auth: AsyncClient,
    db_session: AsyncSession,
):
    """
    SLA unconfirmed: only NEW appointments older than SLA threshold appear.
    - overdue new -> in response
    - fresh new -> not in response
    - old but not new (e.g. confirmed) -> not in response
    """
    shop = (await db_session.execute(select(Shop).where(Shop.tenant_id == 1))).scalar_one()
    service = (await db_session.execute(select(Service).where(Service.tenant_id == 1))).scalar_one()
    db_client = (await db_session.execute(select(Client).where(Client.tenant_id == 1))).scalar_one()

    now = datetime.now(timezone.utc)
    overdue_time = now - timedelta(minutes=20)
    base_end = overdue_time + timedelta(minutes=60)

    # 1. Overdue NEW — created 20 min ago, status new -> must be in response
    appt_overdue_new = Appointment(
        tenant_id=1,
        shop_id=shop.id,
        client_id=db_client.id,
        service_id=service.id,
        start_time=overdue_time,
        end_time=base_end,
        status=AppointmentStatus.NEW,
        created_at=overdue_time,
    )
    db_session.add(appt_overdue_new)

    # 2. Fresh NEW — created now, status new -> must NOT be in response
    appt_fresh_new = Appointment(
        tenant_id=1,
        shop_id=shop.id,
        client_id=db_client.id,
        service_id=service.id,
        start_time=now,
        end_time=now + timedelta(minutes=60),
        status=AppointmentStatus.NEW,
        created_at=now,
    )
    db_session.add(appt_fresh_new)

    # 3. Old CONFIRMED — created 20 min ago, status confirmed -> must NOT be in response
    appt_old_confirmed = Appointment(
        tenant_id=1,
        shop_id=shop.id,
        client_id=db_client.id,
        service_id=service.id,
        start_time=overdue_time,
        end_time=base_end,
        status=AppointmentStatus.CONFIRMED,
        created_at=overdue_time,
    )
    db_session.add(appt_old_confirmed)

    await db_session.commit()

    res = await client_auth.get(f"{settings.API_V1_STR}/sla/unconfirmed?minutes=15")
    assert res.status_code == 200
    data = res.json()

    ids_in_response = [a["appointment_id"] for a in data]
    assert appt_overdue_new.id in ids_in_response
    assert appt_fresh_new.id not in ids_in_response
    assert appt_old_confirmed.id not in ids_in_response
    assert len(data) == 1
    assert data[0]["appointment_id"] == appt_overdue_new.id
    assert data[0]["client_name"] == db_client.full_name


@pytest.mark.asyncio
async def test_sla_unconfirmed_limit_validation(client_auth: AsyncClient):
    """limit must be 1..100: limit=0 and limit=101 return 422, limit=50 returns 200."""
    res_0 = await client_auth.get(f"{settings.API_V1_STR}/sla/unconfirmed?limit=0")
    assert res_0.status_code == 422, f"limit=0: expected 422, got {res_0.status_code}, body={res_0.json()}"

    res_101 = await client_auth.get(f"{settings.API_V1_STR}/sla/unconfirmed?limit=101")
    assert res_101.status_code == 422, f"limit=101: expected 422, got {res_101.status_code}, body={res_101.json()}"

    res_50 = await client_auth.get(f"{settings.API_V1_STR}/sla/unconfirmed?limit=50")
    assert res_50.status_code == 200, f"limit=50: expected 200, got {res_50.status_code}, body={res_50.json()}"
    assert isinstance(res_50.json(), list)
