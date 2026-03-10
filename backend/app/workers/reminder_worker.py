import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.services.reminder_service import (
    send_evening_reminders,
    send_morning_reminders,
    send_one_hour_reminders,
)

logger = logging.getLogger(__name__)


async def run_reminder_worker(
    *,
    poll_interval_seconds: float = 60.0,
) -> None:
    last_morning_date = None
    last_evening_date = None
    last_hourly_slot = None

    tz = ZoneInfo(settings.SHOP_TIMEZONE)

    while True:
        try:
            now = datetime.now(tz)
            current_date = now.date()
            current_hour = now.hour
            current_minute = now.minute

            if current_hour == 8 and current_minute in (0, 1) and last_morning_date != current_date:
                await send_morning_reminders()
                last_morning_date = current_date

            if current_hour == 20 and current_minute in (0, 1) and last_evening_date != current_date:
                await send_evening_reminders()
                last_evening_date = current_date

            hourly_slot = now.strftime("%Y-%m-%d %H:%M")
            if current_minute == 0 and last_hourly_slot != hourly_slot:
                await send_one_hour_reminders()
                last_hourly_slot = hourly_slot

        except Exception as exc:
            logger.exception("Reminder worker iteration failed: %s", exc)

        await asyncio.sleep(poll_interval_seconds)
