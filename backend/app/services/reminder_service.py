import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.db.session import async_session_local
from app.models.models import Appointment, AppointmentStatus

logger = logging.getLogger(__name__)

REMIND_STATUSES = {AppointmentStatus.NEW, AppointmentStatus.CONFIRMED}


def _format_time(dt: datetime) -> str:
    tz = ZoneInfo(settings.SHOP_TIMEZONE)
    local_dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    return local_dt.strftime("%d.%m.%Y в %H:%M")


async def _fetch_appointments_for_date(target_date) -> list:
    """Returns confirmed/new appointments for a given local date (naive UTC range)."""
    tz = ZoneInfo(settings.SHOP_TIMEZONE)

    start_local = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=tz)
    end_local = start_local + timedelta(days=1)

    # Convert to naive UTC for DB comparison
    start_utc = start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    end_utc = end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    async with async_session_local() as db:
        stmt = (
            select(Appointment)
            .options(joinedload(Appointment.client), joinedload(Appointment.service))
            .where(
                and_(
                    Appointment.start_time >= start_utc,
                    Appointment.start_time < end_utc,
                    Appointment.status.in_(REMIND_STATUSES),
                )
            )
        )
        result = await db.execute(stmt)
        return result.scalars().all()


async def send_evening_reminders():
    """Runs at 20:00 — reminds clients about tomorrow's appointment."""
    from app.services.notification_service import NotificationService

    tz = ZoneInfo(settings.SHOP_TIMEZONE)
    tomorrow = (datetime.now(tz) + timedelta(days=1)).date()

    logger.info(f"[Reminder] Evening job: fetching appointments for {tomorrow}")
    appointments = await _fetch_appointments_for_date(tomorrow)

    sent = 0
    for appt in appointments:
        if not appt.client or not appt.client.telegram_id:
            continue
        service_name = appt.service.name if appt.service else "услугу"
        time_str = _format_time(appt.start_time)
        text = (
            f"🔔 <b>Напоминание!</b>\n\n"
            f"Завтра <b>{time_str}</b> у вас запись:\n"
            f"🔧 <b>{service_name}</b>\n\n"
            f"Ждём вас! Если планы изменились — свяжитесь с нами заранее."
        )
        await NotificationService.send_raw_message(appt.client.telegram_id, text)
        sent += 1

    logger.info(f"[Reminder] Evening: sent {sent} reminders for {tomorrow}")


async def send_morning_reminders():
    """Runs at 08:00 — reminds clients about today's appointment."""
    from app.services.notification_service import NotificationService

    tz = ZoneInfo(settings.SHOP_TIMEZONE)
    today = datetime.now(tz).date()

    logger.info(f"[Reminder] Morning job: fetching appointments for {today}")
    appointments = await _fetch_appointments_for_date(today)

    sent = 0
    for appt in appointments:
        if not appt.client or not appt.client.telegram_id:
            continue
        service_name = appt.service.name if appt.service else "услугу"
        time_str = _format_time(appt.start_time)
        text = (
            f"🌅 <b>Доброе утро!</b>\n\n"
            f"Сегодня <b>{time_str}</b> у вас запись:\n"
            f"🔧 <b>{service_name}</b>\n\n"
            f"Будем ждать вас!"
        )
        await NotificationService.send_raw_message(appt.client.telegram_id, text)
        sent += 1

    logger.info(f"[Reminder] Morning: sent {sent} reminders for {today}")
