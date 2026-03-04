"""
Public slug-based endpoints.
All routes live under /{slug}/... and resolve the tenant via the slug path parameter.
"""
from datetime import date, datetime, timedelta, timezone as tz
from typing import List, Optional
from zoneinfo import ZoneInfo
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.slots import get_available_slots
from app.core.tenant_resolver import get_tenant_id_by_slug
from app.db.session import get_db
from app.bot.tenant import get_tenant_shop
from app.models.models import (
    Appointment,
    AppointmentStatus,
    Client,
    Service,
    Tenant,
)
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)

router = APIRouter()


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class ServiceRead(BaseModel):
    id: int
    name: str
    duration_minutes: int
    base_price: float

    class Config:
        from_attributes = True


class ClientCarInfo(BaseModel):
    full_name: str
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None

    class Config:
        from_attributes = True


class PublicBookingCreate(BaseModel):
    service_id: int
    date: str
    telegram_id: int
    full_name: str
    appointment_id: Optional[int] = None
    is_waitlist: bool = False
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None
    timezone: Optional[str] = None


class ClientShort(BaseModel):
    id: int
    full_name: str
    phone: Optional[str]
    telegram_id: Optional[int]

    class Config:
        from_attributes = True


class ServiceShort(BaseModel):
    id: int
    name: str
    duration_minutes: int
    base_price: float

    class Config:
        from_attributes = True


class AppointmentRead(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    status: str
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None
    client: Optional[ClientShort] = None
    service: Optional[ServiceShort] = None

    class Config:
        from_attributes = True


# ─── GET /services/public ─────────────────────────────────────────────────────

@router.get("/services/public", response_model=List[ServiceRead])
@limiter.limit("60/minute")
async def get_public_services(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Service)
        .where(Service.tenant_id == tenant_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


# ─── GET /slots/public ────────────────────────────────────────────────────────

@router.get("/slots/public", response_model=List[datetime])
@limiter.limit("30/minute")
async def get_public_slots(
    request: Request,
    service_duration: int,
    target_date: date = Query(..., description="Date (YYYY-MM-DD)"),
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
    tenant = (await db.execute(tenant_stmt)).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Сервис не найден")

    shop = await get_tenant_shop(db, tenant)
    if not shop:
        raise HTTPException(status_code=400, detail="Сервис временно недоступен")

    return await get_available_slots(shop.id, service_duration, target_date, db)


# ─── POST /appointments/public ────────────────────────────────────────────────

@router.post("/appointments/public", response_model=AppointmentRead)
@limiter.limit("10/minute")
async def create_public_appointment(
    request: Request,
    payload: PublicBookingCreate,
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    try:
        # 1. Parse date
        try:
            start_time = datetime.fromisoformat(payload.date.replace("Z", "+00:00"))
        except ValueError:
            start_time = datetime.combine(datetime.fromisoformat(payload.date).date(), datetime.min.time())

        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=tz.utc)
        else:
            start_time = start_time.astimezone(tz.utc)

        start_time_naive = start_time.replace(tzinfo=None)

        # 2. Get Service
        service = await db.get(Service, payload.service_id)
        if not service or service.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Услуга не найдена")

        # 3. Resolve Shop
        tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await db.execute(tenant_stmt)).scalar_one()
        shop = await get_tenant_shop(db, tenant)
        if not shop:
            raise HTTPException(status_code=400, detail="Сервис недоступен. Попробуйте позже")

        # 4. Handle Rescheduling
        existing_appt = None
        if payload.appointment_id:
            stmt = select(Appointment).where(
                and_(Appointment.id == payload.appointment_id, Appointment.tenant_id == tenant_id)
            )
            result = await db.execute(stmt)
            existing_appt = result.scalar_one_or_none()
            if not existing_appt:
                raise HTTPException(status_code=404, detail="Исходная запись не найдена")

        # 5. Slot Validation
        if not payload.is_waitlist:
            available_slots = await get_available_slots(
                shop_id=shop.id,
                service_duration_minutes=service.duration_minutes,
                date=start_time_naive.date(),
                db=db,
                exclude_appointment_id=payload.appointment_id,
            )
            if not any(
                slot == start_time or slot.replace(tzinfo=None) == start_time_naive
                for slot in available_slots
            ):
                raise HTTPException(status_code=400, detail="Выбранное время уже занято")

        # 6. Get/Create Client
        stmt = select(Client).where(
            and_(Client.telegram_id == payload.telegram_id, Client.tenant_id == tenant_id)
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()

        if not client:
            client = Client(
                tenant_id=tenant_id,
                telegram_id=payload.telegram_id,
                full_name=payload.full_name,
                phone="unknown",
                car_make=payload.car_make,
                car_year=payload.car_year,
                vin=payload.vin,
            )
            db.add(client)
            await db.flush()
        else:
            if payload.car_make:
                client.car_make = payload.car_make
            if payload.car_year:
                client.car_year = payload.car_year
            if payload.vin:
                client.vin = payload.vin
            if client.full_name == "Guest" and payload.full_name:
                client.full_name = payload.full_name

        # 7. Create/Update Appointment with Collision Protection
        end_time_naive = start_time_naive + timedelta(minutes=service.duration_minutes)
        start_time_utc = start_time
        end_time_utc = end_time_naive.replace(tzinfo=tz.utc)

        if not payload.is_waitlist:
            redis = RedisService.get_redis()
            lock_key = f"booking_lock:{shop.id}:{start_time_utc.isoformat()}"
            is_locked = await redis.set(lock_key, "1", nx=True, ex=10)
            if not is_locked:
                raise HTTPException(
                    status_code=409,
                    detail="Это время сейчас бронируется. Попробуйте еще раз",
                )

            try:
                stmt_collide = select(Appointment).where(
                    and_(
                        Appointment.shop_id == shop.id,
                        Appointment.status != AppointmentStatus.CANCELLED,
                        Appointment.status != AppointmentStatus.WAITLIST,
                        Appointment.start_time < end_time_utc,
                        Appointment.end_time > start_time_utc,
                    )
                )
                if payload.appointment_id:
                    stmt_collide = stmt_collide.where(Appointment.id != payload.appointment_id)

                res_collide = await db.execute(stmt_collide)
                if res_collide.scalars().first():
                    raise HTTPException(status_code=409, detail="Это время уже занято")
            finally:
                if not payload.appointment_id:
                    await redis.delete(lock_key)

        status_val = AppointmentStatus.WAITLIST if payload.is_waitlist else (
            AppointmentStatus.CONFIRMED if payload.appointment_id else AppointmentStatus.NEW
        )

        if existing_appt:
            existing_appt.service_id = payload.service_id
            existing_appt.start_time = start_time_utc
            existing_appt.end_time = end_time_utc
            existing_appt.status = status_val
            existing_appt.car_make = payload.car_make
            existing_appt.car_year = payload.car_year
            existing_appt.vin = payload.vin
            appt = existing_appt
        else:
            appt = Appointment(
                tenant_id=tenant_id,
                shop_id=shop.id,
                client_id=client.id,
                service_id=payload.service_id,
                start_time=start_time_utc,
                end_time=end_time_utc,
                status=status_val,
                car_make=payload.car_make,
                car_year=payload.car_year,
                vin=payload.vin,
            )
            db.add(appt)

        await db.commit()

        # Re-fetch with relations
        stmt = select(Appointment).options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
        ).where(and_(Appointment.id == appt.id, Appointment.tenant_id == tenant_id))
        result = await db.execute(stmt)
        appt = result.scalar_one()

        # 8. Notifications
        from app.services.notification_service import NotificationService
        import asyncio

        display_tz = payload.timezone or settings.SHOP_TIMEZONE
        try:
            tz_obj = ZoneInfo(display_tz)
            local_time = start_time.astimezone(tz_obj)
        except Exception:
            local_time = start_time
        time_str = local_time.strftime("%d.%m.%Y %H:%M")

        async def notify():
            try:
                msg = f"✅ <b>Запись подтверждена!</b>\n\n🔧 <b>Услуга:</b> {service.name}\n🕐 <b>Время:</b> {time_str}"
                if payload.is_waitlist:
                    msg = f"📝 <b>Лист ожидания</b>\n\n🔧 <b>Услуга:</b> {service.name}\n📅 <b>Дата:</b> {start_time_naive.strftime('%d.%m.%Y')}"

                await NotificationService.send_booking_confirmation(payload.telegram_id, msg, payload.telegram_id)

                if not payload.is_waitlist and settings.ADMIN_CHAT_ID and str(settings.ADMIN_CHAT_ID) != str(payload.telegram_id):
                    admin_msg = f"🆕 <b>Новая запись! (WebApp)</b>\n\n👤 {payload.full_name}\n🔧 {service.name}\n🕐 {time_str}"
                    await NotificationService.notify_admin(admin_msg)
            except Exception as e:
                logger.error(f"Notification error: {e}")

        asyncio.create_task(notify())

        # 9. Redis Sync
        try:
            redis = RedisService.get_redis()
            event_type = "WAITLIST_ADD" if payload.is_waitlist else (
                "APPOINTMENT_UPDATED" if payload.appointment_id else "NEW_APPOINTMENT"
            )
            broadcast_message = {
                "type": event_type,
                "data": {
                    "id": appt.id,
                    "shop_id": appt.shop_id,
                    "start_time": appt.start_time.isoformat(),
                    "status": appt.status.value,
                },
            }
            await redis.publish(f"appointments_updates:{tenant_id}", json.dumps(broadcast_message))
        except Exception as e:
            logger.error(f"Redis publish error: {e}")

        return appt

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Public booking error: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервиса")


# ─── GET /clients/public ──────────────────────────────────────────────────────

@router.get("/clients/public", response_model=ClientCarInfo)
@limiter.limit("30/minute")
async def get_public_client_car_info(
    request: Request,
    telegram_id: int = Query(...),
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Client).where(
        and_(Client.telegram_id == telegram_id, Client.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()

    if not client or not client.car_make:
        raise HTTPException(status_code=404, detail="Client not found or no car data")

    return client
