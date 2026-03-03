import logging
from typing import Optional

from app.bot.loader import bot
from app.core.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    async def send_raw_message(chat_id: int, text: str):
        """Sends a generic text message to a specific chat."""
        if not chat_id: return
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send raw message to {chat_id}: {e}")

    @staticmethod
    async def send_booking_confirmation(chat_id: int, text: str, telegram_id: Optional[int] = None):
        """Send confirmation and switch to main menu keyboard."""
        if not chat_id:
            return
        try:
            from app.bot.keyboards import get_main_keyboard
            tid = telegram_id or chat_id
            await bot.send_message(
                chat_id, text, parse_mode="HTML",
                reply_markup=get_main_keyboard(tid)
            )
        except Exception as e:
            logger.error(f"Failed to send booking confirmation to {chat_id}: {e}")

    @staticmethod
    async def notify_admin(text: str):
        """Sends a notification to the configured ADMIN_CHAT_ID."""
        if not settings.ADMIN_CHAT_ID: return
        try:
            await bot.send_message(settings.ADMIN_CHAT_ID, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

    @staticmethod
    async def notify_client_status_change(chat_id: int, service_name: str, new_status: str):
        """
        Sends a notification to the client about their appointment status change.
        """
        if not chat_id:
            return

        status_messages = {
            "confirmed": f"✅ Ваша запись на услугу «{service_name}» подтверждена!",
            "in_progress": f"🔧 Мастер приступил к работе над вашим автомобилем («{service_name}»).",
            "completed": f"🎉 Ваш автомобиль готов! Услуга «{service_name}» выполнена. Ждем вас!",
            "cancelled": f"🚫 К сожалению, ваша запись на «{service_name}» была отменена. Пожалуйста, свяжитесь с нами для уточнения."
        }

        message = status_messages.get(new_status)
        if not message:
            return

        try:
            await bot.send_message(chat_id, message)
            logger.info(f"Notification sent to {chat_id} for status {new_status}")
        except Exception as e:
            logger.error(f"Failed to send notification to {chat_id}: {e}")
