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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.config import settings
from app.core.rate_limit import PUBLIC_BOOKING_RATE_LIMIT, limiter
from app.core.slots import get_available_slots
from app.core.tenant_resolver import get_tenant_id_by_slug
from app.db.session import get_db, async_session_local
from app.bot.tenant import get_tenant_shop
from app.models.models import (
    Appointment,
    AppointmentHistory,
    AppointmentStatus,
    Client,
    Service,
    Tenant,
)
from app.models.appointment_intake import AppointmentIntake
from app.schemas.appointment_intake import AppointmentIntakeRead
from app.api.endpoints.appointments import AppointmentIntakeAnswersUpdate
from app.models.auto_extensions import ClientAutoProfile, AppointmentAutoSnapshot
from app.services.audit_service import log_audit
from app.services.outbox_service import enqueue_appointment_created_event, enqueue_appointment_updated_event
from app.services.redis_service import RedisService
from app.services.usage_service import check_appointments_limit, LimitExceededError
from fastapi import status

logger = logging.getLogger(__name__)

router = APIRouter()

TERMINAL_STATUSES = (
    AppointmentStatus.COMPLETED,
    AppointmentStatus.CANCELLED,
    AppointmentStatus.NO_SHOW,
)

_SENTINEL = object()


def _upsert_appointment_auto_snapshot(
    db: AsyncSession,
    appt: Appointment,
    car_make: Optional[str],
    car_year: Optional[int],
    vin: Optional[str],
    existing_snapshot: Optional[AppointmentAutoSnapshot] = _SENTINEL,
) -> None:
    """Create or update AppointmentAutoSnapshot. Skips if all fields are None.
    Pass existing_snapshot explicitly (None for new appt, loaded snapshot for existing)
    to avoid lazy-load (async greenlet error)."""
    if car_make is None and car_year is None and vin is None:
        return
    sn = getattr(appt, "auto_snapshot", None) if existing_snapshot is _SENTINEL else existing_snapshot
    if sn is None:
        sn = AppointmentAutoSnapshot(
            appointment_id=appt.id,
            car_make=car_make,
            car_year=car_year,
            vin=vin,
        )
        db.add(sn)
    else:
        if car_make is not None:
            sn.car_make = car_make
        if car_year is not None:
            sn.car_year = car_year
        if vin is not None:
            sn.vin = vin


def _enrich_appointment_auto_fields(appt: Appointment) -> None:
    """Set auto_info on appt from auto_snapshot for AppointmentRead serialization."""
    sn = getattr(appt, "auto_snapshot", None)
    setattr(
        appt,
        "auto_info",
        AppointmentAutoInfo(
            car_make=sn.car_make if sn else None,
            car_year=sn.car_year if sn else None,
            vin=sn.vin if sn else None,
        ),
    )


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class AppointmentAutoInfo(BaseModel):
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None


class ServiceRead(BaseModel):
    id: int
    name: str
    duration_minutes: int
    base_price: float

    class Config:
        from_attributes = True


class ClientCarInfo(BaseModel):
    full_name: str
    auto_info: Optional[AppointmentAutoInfo] = None

    class Config:
        from_attributes = True


class PublicBookingCreate(BaseModel):
    service_id: int
    date: str
    telegram_id: int
    full_name: str
    appointment_id: Optional[int] = None
    is_waitlist: bool = False
    auto_info: Optional[AppointmentAutoInfo] = None
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
    auto_info: Optional[AppointmentAutoInfo] = None
    integration_status: Optional[str] = None
    last_integration_error: Optional[str] = None
    last_integration_attempt_at: Optional[datetime] = None
    client: Optional[ClientShort] = None
    service: Optional[ServiceShort] = None
    intake: Optional[AppointmentIntakeRead] = None

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
@limiter.limit(PUBLIC_BOOKING_RATE_LIMIT)
async def create_public_appointment(
    request: Request,
    payload: PublicBookingCreate,
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    try:
        redis = None
        lock_acquired = False
        lock_key = None
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
        tenant_stmt = select(Tenant).options(joinedload(Tenant.tariff_plan)).where(Tenant.id == tenant_id)
        tenant = (await db.execute(tenant_stmt)).scalar_one()
        shop = await get_tenant_shop(db, tenant)
        if not shop:
            raise HTTPException(status_code=400, detail="Сервис недоступен. Попробуйте позже")

        # 3b. SaaS limit: new appointments only (not rescheduling)
        from app.services.usage_service import check_appointments_limit, LimitExceededError

        if not payload.appointment_id:
            plan_name = tenant.tariff_plan.name if tenant.tariff_plan else None
            try:
                await check_appointments_limit(db, tenant_id, plan_name)
            except LimitExceededError as e:
                raise HTTPException(
                    status_code=403,
                    detail=e.to_detail(),
                )

        # 4. Handle Rescheduling
        existing_appt = None
        if payload.appointment_id:
            stmt = select(Appointment).options(
                selectinload(Appointment.auto_snapshot),
            ).where(
                and_(
                    Appointment.id == payload.appointment_id,
                    Appointment.tenant_id == tenant_id,
                    Appointment.deleted_at.is_(None),
                )
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
        # Anonymous browser users (telegram_id=0) need tenant-specific pseudo ID to avoid unique constraint
        effective_tg_id = payload.telegram_id if payload.telegram_id else -(tenant_id * 1_000_000)

        stmt = (
            select(Client)
            .where(
                and_(
                    Client.telegram_id == effective_tg_id,
                    Client.tenant_id == tenant_id,
                    Client.deleted_at.is_(None),
                )
            )
            .options(selectinload(Client.auto_profile))
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()

        client_is_new = False
        client_before: Optional[dict] = None
        client_updated = False

        ai = payload.auto_info
        ai_make = ai.car_make if ai else None
        ai_year = ai.car_year if ai else None
        ai_vin = ai.vin if ai else None

        def _profile_car_dict(profile: Optional[ClientAutoProfile]) -> dict:
            if not profile:
                return {"car_make": None, "car_year": None, "vin": None}
            return {"car_make": profile.car_make, "car_year": profile.car_year, "vin": profile.vin}

        if not client:
            client = Client(
                tenant_id=tenant_id,
                telegram_id=effective_tg_id,
                full_name=payload.full_name,
                phone="unknown",
            )
            db.add(client)
            await db.flush()
            if ai_make or ai_year or ai_vin:
                profile = ClientAutoProfile(
                    client_id=client.id,
                    car_make=ai_make,
                    car_year=ai_year,
                    vin=ai_vin,
                )
                db.add(profile)
            client_is_new = True
        else:
            profile = client.auto_profile
            client_before = {"id": client.id, "full_name": client.full_name, **_profile_car_dict(profile)}
            if ai_make or ai_year or ai_vin:
                if profile:
                    if ai_make is not None:
                        profile.car_make = ai_make
                    if ai_year is not None:
                        profile.car_year = ai_year
                    if ai_vin is not None:
                        profile.vin = ai_vin
                else:
                    profile = ClientAutoProfile(
                        client_id=client.id,
                        car_make=ai_make,
                        car_year=ai_year,
                        vin=ai_vin,
                    )
                    db.add(profile)
            if client.full_name == "Guest" and payload.full_name:
                client.full_name = payload.full_name
            client_updated = bool(
                ai_make or ai_year or ai_vin
                or (client_before["full_name"] == "Guest" and payload.full_name)
            )

        # 7. Create/Update Appointment with Collision Protection
        end_time_naive = start_time_naive + timedelta(minutes=service.duration_minutes)
        start_time_utc = start_time
        end_time_utc = end_time_naive.replace(tzinfo=tz.utc)

        if not payload.is_waitlist:
            redis = None
            lock_key = f"booking_lock:{shop.id}:{start_time_utc.isoformat()}"
            lock_acquired = False

            try:
                redis = RedisService.get_redis()
                lock_acquired = bool(await redis.set(lock_key, "1", nx=True, ex=10))
                if not lock_acquired:
                    raise HTTPException(
                        status_code=409,
                        detail="Это время сейчас бронируется. Попробуйте еще раз",
                    )
            except HTTPException:
                raise
            except Exception as redis_error:
                logger.warning(
                    "Public booking lock layer unavailable, falling back to DB overlap check only: %s",
                    redis_error,
                )
                redis = None

            try:
                stmt_collide = select(Appointment).where(
                    and_(
                        Appointment.shop_id == shop.id,
                        Appointment.deleted_at.is_(None),
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
                if False:
                    try:
                        await redis.delete(lock_key)
                    except Exception as redis_error:
                        logger.warning(
                            "Public booking lock release failed for %s: %s",
                            lock_key,
                            redis_error,
                        )

        status_val = AppointmentStatus.WAITLIST if payload.is_waitlist else (
            AppointmentStatus.CONFIRMED if payload.appointment_id else AppointmentStatus.NEW
        )

        appt_before: Optional[dict] = None
        if existing_appt:
            sn_old = getattr(existing_appt, "auto_snapshot", None)
            old_status = existing_appt.status
            appt_before = {
                "id": existing_appt.id,
                "service_id": existing_appt.service_id,
                "start_time": existing_appt.start_time.isoformat() if existing_appt.start_time else None,
                "end_time": existing_appt.end_time.isoformat() if existing_appt.end_time else None,
                "status": old_status.value if old_status else None,
                "car_make": sn_old.car_make if sn_old else None,
                "car_year": sn_old.car_year if sn_old else None,
                "vin": sn_old.vin if sn_old else None,
            }
            existing_appt.service_id = payload.service_id
            existing_appt.start_time = start_time_utc
            existing_appt.end_time = end_time_utc
            existing_appt.status = status_val
            _upsert_appointment_auto_snapshot(
                db, existing_appt,
                ai_make, ai_year, ai_vin,
                existing_snapshot=getattr(existing_appt, "auto_snapshot", None),
            )
            db.add(
                AppointmentHistory(
                    appointment_id=existing_appt.id,
                    tenant_id=tenant_id,
                    old_status=old_status.value,
                    new_status=status_val.value,
                    changed_by_user_id=None,
                    source="public",
                )
            )
            appt = existing_appt
            await enqueue_appointment_updated_event(
                db,
                tenant_id=tenant_id,
                appointment_id=appt.id,
            )
        else:
            appt = Appointment(
                tenant_id=tenant_id,
                shop_id=shop.id,
                client_id=client.id,
                service_id=payload.service_id,
                start_time=start_time_utc,
                end_time=end_time_utc,
                status=status_val,
            )
            db.add(appt)
            await db.flush()
            intake = AppointmentIntake(
                appointment_id=appt.id,
                status="pending",
            )
            db.add(intake)
            await enqueue_appointment_created_event(
                db,
                tenant_id=tenant_id,
                appointment_id=appt.id,
            )
            _upsert_appointment_auto_snapshot(
                db, appt,
                ai_make, ai_year, ai_vin,
                existing_snapshot=None,
            )

        # Audit: client create/update
        if client_is_new or (ai_make or ai_year or ai_vin):
            car_after = {"car_make": ai_make, "car_year": ai_year, "vin": ai_vin}
        elif client_before:
            car_after = {"car_make": client_before["car_make"], "car_year": client_before["car_year"], "vin": client_before["vin"]}
        else:
            car_after = {"car_make": None, "car_year": None, "vin": None}

        if client_is_new:
            await log_audit(
                db,
                tenant_id=tenant_id,
                actor_user_id=None,
                action="create",
                entity_type="client",
                entity_id=str(client.id),
                payload_after={"full_name": client.full_name, **car_after},
                source="public",
            )
        elif client_updated and client_before:
            await log_audit(
                db,
                tenant_id=tenant_id,
                actor_user_id=None,
                action="update",
                entity_type="client",
                entity_id=str(client.id),
                payload_before=client_before,
                payload_after={"full_name": client.full_name, **car_after},
                source="public",
            )

        # Audit: appointment create/update
        car_after_appt = {"car_make": ai_make, "car_year": ai_year, "vin": ai_vin}
        if existing_appt and appt_before:
            await log_audit(
                db,
                tenant_id=tenant_id,
                actor_user_id=None,
                action="update",
                entity_type="appointment",
                entity_id=str(appt.id),
                payload_before=appt_before,
                payload_after={
                    "service_id": appt.service_id,
                    "start_time": appt.start_time.isoformat() if appt.start_time else None,
                    "end_time": appt.end_time.isoformat() if appt.end_time else None,
                    "status": appt.status.value if appt.status else None,
                    **car_after_appt,
                },
                source="public",
            )
        else:
            await log_audit(
                db,
                tenant_id=tenant_id,
                actor_user_id=None,
                action="create",
                entity_type="appointment",
                entity_id=str(appt.id),
                payload_after={
                    "service_id": appt.service_id,
                    "start_time": appt.start_time.isoformat() if appt.start_time else None,
                    "status": appt.status.value if appt.status else None,
                },
                source="public",
            )

        await db.commit()

        if not payload.is_waitlist and redis and lock_acquired:
            try:
                await redis.delete(lock_key)
            except Exception as redis_error:
                logger.warning(
                    "Public booking lock release failed for %s: %s",
                    lock_key,
                    redis_error,
                )

        # Re-fetch with relations (include client.auto_profile to avoid lazy-load greenlet error)
        stmt = select(Appointment).options(
            joinedload(Appointment.client).selectinload(Client.auto_profile),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
            selectinload(Appointment.intake),
        ).where(and_(Appointment.id == appt.id, Appointment.tenant_id == tenant_id))
        result = await db.execute(stmt)
        refreshed_appt = result.scalar_one_or_none()
        if refreshed_appt is not None:
            appt = refreshed_appt
        else:
            logger.warning(
                "Public booking reread failed after commit, returning in-memory appointment id=%s tenant_id=%s",
                appt.id,
                tenant_id,
            )
            appt.client = client
            appt.service = service

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
                recipient_roles = ["client"]
                if not payload.is_waitlist and settings.ADMIN_CHAT_ID and str(settings.ADMIN_CHAT_ID) != str(payload.telegram_id):
                    recipient_roles.append("manager")
                recipient_ids = {"client_telegram_id": payload.telegram_id}
                if settings.ADMIN_CHAT_ID:
                    recipient_ids["manager_chat_id"] = settings.ADMIN_CHAT_ID

                async with async_session_local() as db:
                    await NotificationService.dispatch(
                        db,
                        event_type="appointment_created",
                        appointment_id=appt.id,
                        tenant_id=tenant_id,
                        recipient_roles=recipient_roles,
                        recipient_ids=recipient_ids,
                        context={
                            "service_name": service.name,
                            "slot_time": time_str,
                            "date_str": start_time_naive.strftime("%d.%m.%Y"),
                            "is_waitlist": payload.is_waitlist,
                            "client_name": payload.full_name,
                        },
                    )
            except Exception as e:
                logger.error(f"Notification error: {e}")

        try:
            asyncio.create_task(notify())
        except Exception as task_error:
            logger.error(f"Notification task scheduling error: {task_error}")

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

        _enrich_appointment_auto_fields(appt)
        return appt

    except HTTPException:
        if not payload.is_waitlist and redis and lock_acquired:
            try:
                await redis.delete(lock_key)
            except Exception as redis_error:
                logger.warning(
                    "Public booking lock release failed for %s: %s",
                    lock_key,
                    redis_error,
                )
        raise
    except IntegrityError as e:
        if not payload.is_waitlist and redis and lock_acquired:
            try:
                await redis.delete(lock_key)
            except Exception as redis_error:
                logger.warning(
                    "Public booking lock release failed for %s: %s",
                    lock_key,
                    redis_error,
                )
        logger.warning("Booking overlap detected at DB level: %s", e)
        raise HTTPException(
            status_code=409,
            detail="Это время уже занято. Пожалуйста выберите другой слот",
        )
    except Exception as e:
        if not payload.is_waitlist and redis and lock_acquired:
            try:
                await redis.delete(lock_key)
            except Exception as redis_error:
                logger.warning(
                    "Public booking lock release failed for %s: %s",
                    lock_key,
                    redis_error,
                )
        logger.error("Public booking error: %s", e)
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервиса")


# ─── GET /appointments/public/current ──────────────────────────────────────────

@router.get("/appointments/public/current", response_model=AppointmentRead)
@limiter.limit("30/minute")
async def get_public_current_appointment(
    request: Request,
    telegram_id: int = Query(...),
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Client)
        .where(
            and_(
                Client.telegram_id == telegram_id,
                Client.tenant_id == tenant_id,
                Client.deleted_at.is_(None),
            )
        )
    )
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    appt_stmt = (
        select(Appointment)
        .where(
            and_(
                Appointment.client_id == client.id,
                Appointment.tenant_id == tenant_id,
                Appointment.deleted_at.is_(None),
                Appointment.status.notin_(TERMINAL_STATUSES),
            )
        )
        .options(
            joinedload(Appointment.client).selectinload(Client.auto_profile),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
            selectinload(Appointment.intake),
        )
        .order_by(Appointment.start_time)
        .limit(1)
    )
    appt_result = await db.execute(appt_stmt)
    appt = appt_result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Активная запись не найдена")

    _enrich_appointment_auto_fields(appt)
    return appt


@router.get("/appointments/public/{appointment_id}/intake", response_model=AppointmentIntakeRead)
@limiter.limit("30/minute")
async def get_public_appointment_intake(
    request: Request,
    appointment_id: int,
    telegram_id: int = Query(...),
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.intake))
        .join(Client, Appointment.client_id == Client.id)
        .where(
            and_(
                Appointment.id == appointment_id,
                Appointment.tenant_id == tenant_id,
                Appointment.deleted_at.is_(None),
                Client.telegram_id == telegram_id,
                Client.tenant_id == tenant_id,
                Client.deleted_at.is_(None),
            )
        )
    )
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not appt.intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return appt.intake


@router.patch("/appointments/public/{appointment_id}/intake/answers", response_model=AppointmentIntakeRead)
@limiter.limit("30/minute")
async def update_public_appointment_intake_answers(
    request: Request,
    appointment_id: int,
    payload: AppointmentIntakeAnswersUpdate,
    telegram_id: int = Query(...),
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.intake))
        .join(Client, Appointment.client_id == Client.id)
        .where(
            and_(
                Appointment.id == appointment_id,
                Appointment.tenant_id == tenant_id,
                Appointment.deleted_at.is_(None),
                Client.telegram_id == telegram_id,
                Client.tenant_id == tenant_id,
                Client.deleted_at.is_(None),
            )
        )
    )
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not appt.intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    appt.intake.answers_json = payload.answers_json
    await db.commit()
    await db.refresh(appt.intake)
    return appt.intake


# ─── PATCH /appointments/public/cancel ────────────────────────────────────────

@router.patch("/appointments/public/cancel", response_model=AppointmentRead)
@limiter.limit("30/minute")
async def cancel_public_appointment(
    request: Request,
    telegram_id: int = Query(...),
    appointment_id: int = Query(...),
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Client)
        .where(
            and_(
                Client.telegram_id == telegram_id,
                Client.tenant_id == tenant_id,
                Client.deleted_at.is_(None),
            )
        )
    )
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    appt_stmt = (
        select(Appointment)
        .where(
            and_(
                Appointment.id == appointment_id,
                Appointment.client_id == client.id,
                Appointment.tenant_id == tenant_id,
                Appointment.deleted_at.is_(None),
            )
        )
    )
    appt_result = await db.execute(appt_stmt)
    appt = appt_result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    if appt.status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Запись уже в финальном статусе и не может быть отменена",
        )

    old_status = appt.status
    appt.status = AppointmentStatus.CANCELLED

    db.add(
        AppointmentHistory(
            appointment_id=appt.id,
            tenant_id=tenant_id,
            old_status=old_status.value,
            new_status=AppointmentStatus.CANCELLED.value,
            changed_by_user_id=None,
            source="public",
        )
    )

    await enqueue_appointment_updated_event(
        db,
        tenant_id=tenant_id,
        appointment_id=appt.id,
    )

    await db.commit()

    stmt_refresh = (
        select(Appointment)
        .where(
            and_(
                Appointment.id == appt.id,
                Appointment.tenant_id == tenant_id,
            )
        )
        .options(
            joinedload(Appointment.client).selectinload(Client.auto_profile),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
        )
    )
    refreshed = (await db.execute(stmt_refresh)).scalar_one_or_none()
    if refreshed:
        appt = refreshed

    _enrich_appointment_auto_fields(appt)
    return appt


# ─── GET /clients/public ──────────────────────────────────────────────────────

@router.get("/clients/public", response_model=ClientCarInfo)
@limiter.limit("30/minute")
async def get_public_client_car_info(
    request: Request,
    telegram_id: int = Query(...),
    tenant_id: int = Depends(get_tenant_id_by_slug),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Client)
        .where(
            and_(
                Client.telegram_id == telegram_id,
                Client.tenant_id == tenant_id,
                Client.deleted_at.is_(None),
            )
        )
        .options(selectinload(Client.auto_profile))
    )
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()

    profile = client.auto_profile if client else None
    has_car_data = profile and (profile.car_make or profile.car_year or profile.vin)
    if not client or not has_car_data:
        raise HTTPException(status_code=404, detail="Client not found or no car data")

    return ClientCarInfo(
        full_name=client.full_name,
        auto_info=AppointmentAutoInfo(
            car_make=profile.car_make if profile else None,
            car_year=profile.car_year if profile else None,
            vin=profile.vin if profile else None,
        ),
    )
