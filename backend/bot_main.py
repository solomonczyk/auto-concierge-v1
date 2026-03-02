import asyncio
import sys
import logging

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.core.config import settings
from app.bot.loader import bot, dp
from app.bot.handlers import router as bot_router

async def main():
    logger.info("Starting bot standalone...")
    dp.include_router(bot_router)
    
    # Ensure webhook is deleted
    await bot.delete_webhook(drop_pending_updates=True)

    # Set persistent Menu Button for the web app
    from aiogram.types import MenuButtonWebApp, WebAppInfo
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="🔧 Запись",
            web_app=WebAppInfo(url=settings.WEBAPP_URL)
        )
    )
    
    logger.info("Bot is polling...")
    logger.info(f"Starting bot with WEBAPP_URL: {settings.WEBAPP_URL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
