import asyncio
import json
import logging
from datetime import datetime, time as dtime, timedelta, timezone as tz
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.db.session import async_session_local
from app.models.models import (
    Appointment,
    AppointmentStatus,
    Client,
    Service,
    Shop,
    TenantSettings,
)
from app.services.notification_service import NotificationService
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)


def _get_demo_tg_id(tenant_id: int) -> int:
    return -(tenant_id * 1_000_001)


async def create_demo_client(tenant_id: int) -> Client:
    demo_tg_id = _get_demo_tg_id(tenant_id)

    async with async_session_local() as db:
        existing = (
            await db.execute(
                select(Client).where(
                    Client.telegram_id == demo_tg_id,
                    Client.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

        if existing:
            return existing

        client = Client(
            tenant_id=tenant_id,
            telegram_id=demo_tg_id,
            full_name="Иван Петров",
            phone="+70000000000",
            car_make="Toyota Camry",
            car_year=2020,
            vin="A123BC77",
        )
        db.add(client)
        await db.commit()
        await db.refresh(client)
        return client


async def send_tg(client: Client, text: str) -> None:
    chat_id = client.telegram_id if client.telegram_id and client.telegram_id > 0 else settings.ADMIN_CHAT_ID
    if not chat_id:
        logger.warning("Demo message skipped: no chat_id for tenant demo")
        return
    await NotificationService.send_raw_message(chat_id=chat_id, text=text)


async def create_demo_appointment(tenant_id: int, client_id: int) -> Appointment:
    async with async_session_local() as db:
        shop = (await db.execute(select(Shop).where(Shop.tenant_id == tenant_id).limit(1))).scalar_one_or_none()
        if not shop:
            raise ValueError("Demo tenant has no shop")

        service = (await db.execute(select(Service).where(Service.tenant_id == tenant_id).limit(1))).scalar_one_or_none()
        if not service:
            raise ValueError("Demo tenant has no services")

        tz_name = settings.SHOP_TIMEZONE
        tenant_settings = (
            await db.execute(
                select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if tenant_settings and tenant_settings.timezone:
            tz_name = tenant_settings.timezone

        shop_tz = ZoneInfo(tz_name)
        tomorrow = datetime.now(shop_tz).date() + timedelta(days=1)
        start_local = datetime.combine(tomorrow, dtime(hour=10, minute=0), tzinfo=shop_tz)
        start_utc = start_local.astimezone(tz.utc)
        end_utc = start_utc + timedelta(minutes=service.duration_minutes)

        appointment = Appointment(
            tenant_id=tenant_id,
            shop_id=shop.id,
            client_id=client_id,
            service_id=service.id,
            start_time=start_utc,
            end_time=end_utc,
            status=AppointmentStatus.NEW,
            car_make="Toyota Camry",
            car_year=2020,
            vin="A123BC77",
        )
        db.add(appointment)
        await db.commit()
        await db.refresh(appointment)

        redis = RedisService.get_redis()
        await redis.publish(
            f"appointments_updates:{tenant_id}",
            json.dumps(
                {
                    "type": "NEW_APPOINTMENT",
                    "data": {
                        "id": appointment.id,
                        "shop_id": appointment.shop_id,
                        "start_time": appointment.start_time.isoformat(),
                        "status": appointment.status.value,
                    },
                }
            ),
        )

        return appointment


async def move_status(appointment_id: int, new_status: str, tenant_id: int) -> None:
    async with async_session_local() as db:
        stmt = (
            select(Appointment)
            .options(joinedload(Appointment.client), joinedload(Appointment.service))
            .where(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id)
        )
        appt = (await db.execute(stmt)).scalar_one_or_none()
        if not appt:
            logger.warning("Demo: appointment %s not found", appointment_id)
            return

        old_status = appt.status
        appt.status = AppointmentStatus(new_status)
        if appt.status == AppointmentStatus.COMPLETED:
            appt.completed_at = datetime.now(tz.utc)
        elif old_status == AppointmentStatus.COMPLETED:
            appt.completed_at = None

        await db.commit()
        await db.refresh(appt)

        redis = RedisService.get_redis()
        await redis.publish(
            f"appointments_updates:{tenant_id}",
            json.dumps(
                {
                    "type": "STATUS_UPDATE",
                    "data": {
                        "id": appt.id,
                        "shop_id": appt.shop_id,
                        "status": appt.status.value,
                    },
                }
            ),
        )


async def run_demo_workflow(tenant_id: int) -> None:
    try:
        client = await create_demo_client(tenant_id)

        await send_tg(client, "🔍 Анализируем состояние автомобиля...")
        await asyncio.sleep(2)

        await send_tg(client, "⚙️ Подбираем подходящую услугу...")
        await asyncio.sleep(2)

        await send_tg(client, "Рекомендуем услугу: Замена масла и фильтра")

        appointment = await create_demo_appointment(
            tenant_id=tenant_id,
            client_id=client.id,
        )

        await asyncio.sleep(4)

        await move_status(appointment.id, "confirmed", tenant_id)
        await send_tg(client, "Ваша запись подтверждена")

        await asyncio.sleep(5)

        await move_status(appointment.id, "in_progress", tenant_id)
        await send_tg(client, "Ваш автомобиль принят в работу")

        await asyncio.sleep(5)

        await move_status(appointment.id, "completed", tenant_id)
        await send_tg(client, "Работы завершены. Спасибо за обращение!")
    except Exception:
        logger.exception("Demo workflow failed for tenant_id=%s", tenant_id)


async def delete_demo_appointments(tenant_id: int) -> int:
    demo_tg_id = _get_demo_tg_id(tenant_id)
    async with async_session_local() as db:
        demo_client_ids = select(Client.id).where(
            Client.tenant_id == tenant_id,
            Client.telegram_id == demo_tg_id,
        )
        result = await db.execute(
            delete(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.client_id.in_(demo_client_ids),
            )
        )
        await db.commit()
        return int(result.rowcount or 0)


async def delete_demo_clients(tenant_id: int) -> int:
    demo_tg_id = _get_demo_tg_id(tenant_id)
    async with async_session_local() as db:
        result = await db.execute(
            delete(Client).where(
                Client.tenant_id == tenant_id,
                Client.telegram_id == demo_tg_id,
            )
        )
        await db.commit()
        return int(result.rowcount or 0)


async def reset_demo(tenant_id: int) -> dict[str, object]:
    deleted_appointments = await delete_demo_appointments(tenant_id)
    deleted_clients = await delete_demo_clients(tenant_id)

    redis = RedisService.get_redis()
    await redis.publish(
        f"appointments_updates:{tenant_id}",
        json.dumps(
            {
                "type": "DEMO_RESET",
                "data": {
                    "deleted_appointments": deleted_appointments,
                    "deleted_clients": deleted_clients,
                },
            }
        ),
    )

    return {
        "status": "demo_reset",
        "deleted_appointments": deleted_appointments,
        "deleted_clients": deleted_clients,
    }
