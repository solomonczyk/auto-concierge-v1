import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.client import get_bot_by_tenant_id
from app.core.config import settings

logger = logging.getLogger(__name__)

# Маппинг статуса → доменный event для уведомлений (см. APPOINTMENT_NOTIFICATION_CONTRACT)
STATUS_TO_NOTIFICATION_EVENT = {
    "confirmed": "appointment_confirmed",
    "cancelled": "appointment_cancelled",
    "no_show": "appointment_no_show",
    "completed": "appointment_completed",
}


class NotificationService:
    @staticmethod
    async def dispatch(
        db: AsyncSession,
        event_type: str,
        appointment_id: int,
        tenant_id: int,
        recipient_roles: Optional[List[str]] = None,
        recipient_ids: Optional[dict] = None,
        context: Optional[dict] = None,
    ) -> None:
        """
        Единая точка входа для уведомлений по записям.
        См. docs/NOTIFICATION_DISPATCH_RULES.md и docs/APPOINTMENT_NOTIFICATION_CONTRACT.md
        """
        recipient_ids = recipient_ids or {}
        context = context or {}

        service_name = context.get("service_name") or "услугу"

        # appointment_created: клиент + менеджер (менеджер только при !waitlist — контракт)
        if event_type == "appointment_created":
            recipient_roles = recipient_roles or []
            is_waitlist = context.get("is_waitlist", False)
            slot_time = context.get("slot_time") or "—"
            client_name = context.get("client_name") or "—"

            # Клиент: подтверждение или waitlist-текст
            client_telegram_id = recipient_ids.get("client_telegram_id")
            if "client" in recipient_roles and client_telegram_id:
                if is_waitlist:
                    date_str = context.get("date_str") or slot_time
                    client_msg = (
                        f"📝 <b>Лист ожидания</b>\n\n"
                        f"🔧 <b>Услуга:</b> {service_name}\n"
                        f"📅 <b>Дата:</b> {date_str}"
                    )
                else:
                    client_msg = (
                        f"✅ <b>Запись подтверждена!</b>\n\n"
                        f"🔧 <b>Услуга:</b> {service_name}\n"
                        f"🕐 <b>Время:</b> {slot_time}"
                    )
                await NotificationService.send_booking_confirmation(
                    db,
                    tenant_id,
                    client_telegram_id,
                    client_msg,
                    client_telegram_id,
                )

            # Менеджер: только при обычной записи (не waitlist)
            if "manager" in recipient_roles and not is_waitlist:
                manager_chat_id = recipient_ids.get("manager_chat_id")
                manager_msg = (
                    f"🆕 <b>Новая запись! (WebApp)</b>\n\n"
                    f"👤 {client_name}\n🔧 {service_name}\n🕐 {slot_time}"
                )
                if manager_chat_id:
                    await NotificationService.send_raw_message(
                        db,
                        tenant_id,
                        manager_chat_id,
                        manager_msg,
                    )
                elif settings.ADMIN_CHAT_ID:
                    await NotificationService.notify_admin(
                        db,
                        tenant_id,
                        manager_msg,
                    )
            return

        # appointment_no_show: только менеджеру, клиенту ничего (контракт)
        if event_type == "appointment_no_show":
            manager_chat_id = recipient_ids.get("manager_chat_id")
            if manager_chat_id:
                msg = (
                    f"⚠️ <b>Клиент не явился</b>\n\n"
                    f"Запись #{appointment_id}\n"
                    f"Услуга: {service_name}"
                )
                await NotificationService.send_raw_message(
                    db,
                    tenant_id,
                    manager_chat_id,
                    msg,
                )
            elif settings.ADMIN_CHAT_ID:
                msg = (
                    f"⚠️ <b>Клиент не явился</b>\n\n"
                    f"Запись #{appointment_id}\n"
                    f"Услуга: {service_name}"
                )
                await NotificationService.notify_admin(
                    db,
                    tenant_id,
                    msg,
                )
            return

        # Клиентские уведомления (confirmed, cancelled)
        client_telegram_id = recipient_ids.get("client_telegram_id")
        if not client_telegram_id:
            return

        if event_type == "appointment_confirmed":
            await NotificationService.notify_client_status_change(
                db,
                tenant_id,
                client_telegram_id,
                service_name,
                "confirmed",
            )
        elif event_type == "appointment_cancelled":
            await NotificationService.notify_client_status_change(
                db,
                tenant_id,
                client_telegram_id,
                service_name,
                "cancelled",
            )
        elif event_type == "appointment_completed":
            await NotificationService.notify_client_status_change(
                db,
                tenant_id,
                client_telegram_id,
                service_name,
                "completed",
            )

    @staticmethod
    async def send_raw_message(
        db: AsyncSession,
        tenant_id: int,
        chat_id: int,
        text: str,
    ):
        """Sends a generic text message to a specific chat."""
        if not chat_id:
            return
        bot = await get_bot_by_tenant_id(db, tenant_id)
        if bot is None:
            logger.warning("Telegram bot is not configured for tenant_id=%s", tenant_id)
            return
        try:
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send raw message to {chat_id}: {e}")

    @staticmethod
    async def send_booking_confirmation(
        db: AsyncSession,
        tenant_id: int,
        chat_id: int,
        text: str,
        telegram_id: Optional[int] = None,
    ):
        """Send confirmation and switch to main menu keyboard."""
        if not chat_id:
            return
        bot = await get_bot_by_tenant_id(db, tenant_id)
        if bot is None:
            logger.warning("Telegram bot is not configured")
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
    async def notify_admin(
        db: AsyncSession,
        tenant_id: int,
        text: str,
    ):
        """Sends a notification to the configured ADMIN_CHAT_ID."""
        if not settings.ADMIN_CHAT_ID:
            return
        bot = await get_bot_by_tenant_id(db, tenant_id)
        if bot is None:
            logger.warning("Telegram bot is not configured")
            return
        try:
            await bot.send_message(settings.ADMIN_CHAT_ID, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

    @staticmethod
    async def notify_client_status_change(
        db: AsyncSession,
        tenant_id: int,
        chat_id: int,
        service_name: str,
        new_status: str,
    ):
        """
        Sends a notification to the client about their appointment status change.
        """
        if not chat_id:
            return
        bot = await get_bot_by_tenant_id(db, tenant_id)
        if bot is None:
            logger.warning("Telegram bot is not configured")
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
