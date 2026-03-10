"""
Worker process: SLA tasks + reminders. Runs independently of API and bot.
Entrypoint: python -m app.worker
See docs/WORKER_RUNTIME_CONTRACT.md
"""
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.db.session import async_session_local
from app.services.reminder_service import send_evening_reminders, send_morning_reminders, send_one_hour_reminders
from app.services.sla_service import auto_no_show, check_unconfirmed_appointments

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def _run_auto_no_show():
    """Wrapper: create session, run auto_no_show."""
    async with async_session_local() as db:
        return await auto_no_show(db)


async def _run_check_unconfirmed():
    """Wrapper: create session, run check_unconfirmed_appointments."""
    async with async_session_local() as db:
        return await check_unconfirmed_appointments(db)


async def main():
    tz = ZoneInfo(settings.SHOP_TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        _run_auto_no_show,
        IntervalTrigger(minutes=1, timezone=tz),
        id="auto_no_show",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_check_unconfirmed,
        IntervalTrigger(minutes=5, timezone=tz),
        id="check_unconfirmed",
        replace_existing=True,
    )
    scheduler.add_job(
        send_evening_reminders,
        CronTrigger(hour=20, minute=0, timezone=tz),
        id="evening_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        send_morning_reminders,
        CronTrigger(hour=8, minute=0, timezone=tz),
        id="morning_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        send_one_hour_reminders,
        IntervalTrigger(minutes=10, timezone=tz),
        id="one_hour_reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("worker.started scheduler=apscheduler jobs=5")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("worker.shutdown reason=sigterm")
        scheduler.shutdown(wait=True)


if __name__ == "__main__":
    asyncio.run(main())
