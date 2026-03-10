from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.models import Appointment, AppointmentStatus, Client, TenantSettings
from app.services.reminder_service import send_one_hour_reminders


@pytest.mark.asyncio
async def test_send_one_hour_reminders_sends_message(db_session):
    tenant_settings = TenantSettings(
        tenant_id=1,
        timezone="Europe/Moscow",
    )
    db_session.add(tenant_settings)
    await db_session.flush()

    client = await db_session.get(Client, 1)
    client.telegram_id = 123456789
    await db_session.flush()

    appointment = Appointment(
        tenant_id=1,
        shop_id=1,
        client_id=1,
        service_id=1,
        start_time=datetime.now(timezone.utc) + timedelta(minutes=60),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=120),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(appointment)
    await db_session.commit()

    with patch(
        "app.services.notification_service.NotificationService.send_raw_message",
        new_callable=AsyncMock,
    ) as mock_send:
        await send_one_hour_reminders()

    assert mock_send.await_count == 1


@pytest.mark.asyncio
async def test_send_one_hour_reminders_skips_client_without_telegram_id(db_session):
    tenant_settings = TenantSettings(
        tenant_id=1,
        timezone="Europe/Moscow",
    )
    db_session.add(tenant_settings)
    await db_session.flush()

    appointment = Appointment(
        tenant_id=1,
        shop_id=1,
        client_id=1,
        service_id=1,
        start_time=datetime.now(timezone.utc) + timedelta(minutes=60),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=120),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(appointment)
    await db_session.commit()

    with patch(
        "app.services.notification_service.NotificationService.send_raw_message",
        new_callable=AsyncMock,
    ) as mock_send:
        await send_one_hour_reminders()

    assert mock_send.await_count == 0


@pytest.mark.asyncio
async def test_send_one_hour_reminders_skips_deleted_appointment(db_session):
    tenant_settings = TenantSettings(
        tenant_id=1,
        timezone="Europe/Moscow",
    )
    db_session.add(tenant_settings)
    await db_session.flush()

    client = await db_session.get(Client, 1)
    client.telegram_id = 123456789
    await db_session.flush()

    appointment = Appointment(
        tenant_id=1,
        shop_id=1,
        client_id=1,
        service_id=1,
        start_time=datetime.now(timezone.utc) + timedelta(minutes=60),
        end_time=datetime.now(timezone.utc) + timedelta(minutes=120),
        status=AppointmentStatus.CONFIRMED,
        deleted_at=datetime.now(timezone.utc),
    )
    db_session.add(appointment)
    await db_session.commit()

    with patch(
        "app.services.notification_service.NotificationService.send_raw_message",
        new_callable=AsyncMock,
    ) as mock_send:
        await send_one_hour_reminders()

    assert mock_send.await_count == 0
