import asyncio
import sys
import logging

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.core.config import settings
from app.bot.loader import dp
from app.bot.client import get_bot
from app.bot.handlers import router as bot_router


def _start_scheduler():
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from zoneinfo import ZoneInfo
    from app.services.reminder_service import send_evening_reminders, send_morning_reminders

    tz = ZoneInfo(settings.SHOP_TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    # 20:00 — напоминание на завтра
    scheduler.add_job(
        send_evening_reminders,
        CronTrigger(hour=20, minute=0, timezone=tz),
        id="evening_reminders",
        replace_existing=True,
    )

    # 08:00 — напоминание на сегодня
    scheduler.add_job(
        send_morning_reminders,
        CronTrigger(hour=8, minute=0, timezone=tz),
        id="morning_reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Reminder scheduler started (tz={settings.SHOP_TIMEZONE}): 08:00 & 20:00")
    return scheduler


async def main():
    logger.info("Starting bot standalone...")
    dp.include_router(bot_router)

    bot = get_bot()
    if bot is None:
        raise RuntimeError("Telegram bot is not configured")

    await bot.delete_webhook(drop_pending_updates=True)

    from aiogram.types import MenuButtonDefault
    await bot.set_chat_menu_button(menu_button=MenuButtonDefault())

    logger.info(f"Bot is polling... WEBAPP_URL: {settings.WEBAPP_URL}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
