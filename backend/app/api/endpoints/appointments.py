from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone as tz
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import joinedload
from app.db.session import get_db
from app.api import deps
from app.models.models import Appointment, AppointmentStatus, Client, Service, User, UserRole, Tenant, TariffPlan
from app.services.redis_service import RedisService 
from app.services.external_integration_service import external_integration
from app.core.config import settings
from app.core.slots import get_available_slots
from app.bot.tenant import get_tenant_shop
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

class PublicBookingCreate(BaseModel):
    service_id: int
    date: str  # ISO string or YYYY-MM-DD
    telegram_id: int
    full_name: str
    appointment_id: Optional[int] = None
    is_waitlist: bool = False
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None

class AppointmentCreate(BaseModel):
    service_id: int
    start_time: datetime
    # client info (simplified for MVP: creating client on fly or linking)
    client_name: str
    client_phone: str
    client_telegram_id: int = None

class AppointmentRead(BaseModel):
    id: int
    shop_id: int
    service_id: int
    client_id: int
    start_time: datetime
    end_time: datetime
    status: str
    
    class Config:
        from_attributes = True

from pydantic import BaseModel, field_validator

class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus

    @field_validator("status", mode="before")
    @classmethod
    def lowercase_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v

class AppointmentUpdate(BaseModel):
    service_id: int = None
    start_time: datetime = None

@router.patch("/{id}", response_model=AppointmentRead)
async def update_appointment(
    id: int,
    appt_update: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id)
):
    stmt = select(Appointment).where(and_(Appointment.id == id, Appointment.tenant_id == tenant_id))
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()
    
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt_update.service_id:
        service = await db.get(Service, appt_update.service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
        appt.service_id = appt_update.service_id
        # Trigger recalculation of end_time if start_time or service changed
        start = appt_update.start_time or appt.start_time
        appt.end_time = start + timedelta(minutes=service.duration_minutes)
        
    if appt_update.start_time:
        appt.start_time = appt_update.start_time
        # Ensure end_time stays in sync with duration
        service = await db.get(Service, appt.service_id)
        appt.end_time = appt.start_time + timedelta(minutes=service.duration_minutes)

    await db.commit()
    await db.refresh(appt)
    
    # Broadcast update
    redis = RedisService.get_redis()
    message = {
        "type": "APPOINTMENT_UPDATED",
        "data": {
            "id": appt.id,
            "shop_id": appt.shop_id
        }
    }
    await redis.publish("appointments_updates", json.dumps(message))
    
    return appt

@router.post("/", response_model=AppointmentRead)
async def create_appointment(
    appt: AppointmentCreate, 
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
    current_user: User = Depends(deps.require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    # 0. Enforce Tenancy and Tariffs
    shop_id = current_user.shop_id
    
    # Check Tariff Limits
    stmt_count = select(func.count(Appointment.id)).where(
        and_(
            Appointment.tenant_id == tenant_id,
            Appointment.status != AppointmentStatus.CANCELLED
        )
    )
    current_count = (await db.execute(stmt_count)).scalar() or 0
    
    stmt_tenant = select(Tenant).options(joinedload(Tenant.tariff_plan)).where(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt_tenant)).scalar_one()
    
    max_appt = tenant.tariff_plan.max_appointments if tenant.tariff_plan else 10
    if current_count >= max_appt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tariff limit reached ({max_appt} bookings). Please upgrade your plan."
        )

    # 1. Get Service to calculate duration
    service = await db.get(Service, appt.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
        
    # Calculate end_time based on service duration
    end_time = appt.start_time + timedelta(minutes=service.duration_minutes)

    # 2. Race Condition Protection (Soft Lock)
    redis = RedisService.get_redis()
    lock_key = f"booking_lock:{shop_id}:{appt.start_time.isoformat()}"
    
    is_locked = await redis.set(lock_key, "1", nx=True, ex=10)
    if not is_locked:
         raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slot is currently being booked by someone else. Please try again."
        )

    try:
        stmt = select(Appointment).where(
            and_(
                Appointment.shop_id == shop_id,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < end_time,
                Appointment.end_time > appt.start_time
            )
        )
        result = await db.execute(stmt)
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Slot already taken"
            )

        stmt = select(Client).where(and_(Client.phone == appt.client_phone, Client.tenant_id == tenant_id))
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()
        
        if not client:
            client = Client(
                tenant_id=tenant_id,
                full_name=appt.client_name,
                phone=appt.client_phone,
                telegram_id=appt.client_telegram_id
            )
            db.add(client)
            await db.flush()
        
        new_appt = Appointment(
            tenant_id=tenant_id,
            shop_id=shop_id,
            service_id=appt.service_id,
            client_id=client.id,
            start_time=appt.start_time,
            end_time=end_time,
            status=AppointmentStatus.NEW
        )
        
        db.add(new_appt)
        await db.commit()
        await db.refresh(new_appt)
        
        # 3. External Integration Hook (Hardened: Persistent Redis Queue)
        external_integration.enqueue_appointment(new_appt.id, tenant_id)
        
        return new_appt
        
    finally:
        await redis.delete(lock_key)

@router.patch("/{id}/status", response_model=AppointmentRead)
async def update_appointment_status(
    id: int,
    status_update: AppointmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id)
):
    from sqlalchemy.orm import joinedload
    stmt = select(Appointment).options(
        joinedload(Appointment.client),
        joinedload(Appointment.service)
    ).where(and_(Appointment.id == id, Appointment.tenant_id == tenant_id))
    
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()
    
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    old_status = appt.status
    appt.status = status_update.status
    
    await db.commit()
    await db.refresh(appt)
    
    if appt.status != old_status and appt.client.telegram_id:
        from app.services.notification_service import NotificationService
        import asyncio
        
        # Properly handle async notification with error handling
        async def notify_client():
            try:
                await NotificationService.notify_client_status_change(
                    chat_id=appt.client.telegram_id,
                    service_name=appt.service.name,
                    new_status=appt.status.value
                )
            except Exception as notify_error:
                # Log but don't fail the main request
                import logging
                logging.getLogger(__name__).error(
                    f"Failed to send notification for appointment {appt.id}: {notify_error}"
                )
        
        asyncio.create_task(notify_client())
        
    redis = RedisService.get_redis()
    message = {
        "type": "STATUS_UPDATE",
        "data": {
            "id": appt.id,
            "shop_id": appt.shop_id,
            "status": appt.status.value
        }
    }
    await redis.publish("appointments_updates", json.dumps(message))
    
    return appt

@router.get("/", response_model=List[AppointmentRead])
async def read_appointments(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id)
):
    result = await db.execute(select(Appointment).where(Appointment.tenant_id == tenant_id).offset(skip).limit(limit))
    return result.scalars().all()

@router.get("/{id}", response_model=AppointmentRead)
async def read_appointment(
    id: int, 
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id)
):
    """
    Get appointment by ID. Requires authentication.
    Only returns appointments belonging to the current tenant.
    """
    stmt = select(Appointment).where(
        and_(Appointment.id == id, Appointment.tenant_id == tenant_id)
    )
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()
    
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
@router.post("/public", response_model=AppointmentRead)
async def create_public_appointment(
    payload: PublicBookingCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id)
):
    """
    Public endpoint for WebApp bookings. 
    Handles both new appointments and waitlist.
    """
    try:
        # 1. Parse date
        try:
            start_time = datetime.fromisoformat(payload.date.replace("Z", "+00:00"))
        except ValueError:
            start_time = datetime.combine(datetime.fromisoformat(payload.date).date(), datetime.min.time())
        
        start_time_naive = start_time.replace(tzinfo=None)
        
        # 2. Get Service
        service = await db.get(Service, payload.service_id)
        if not service or service.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Service not found")

        # 3. Handle Rescheduling
        existing_appt = None
        if payload.appointment_id:
            stmt = select(Appointment).where(
                and_(Appointment.id == payload.appointment_id, Appointment.tenant_id == tenant_id)
            )
            result = await db.execute(stmt)
            existing_appt = result.scalar_one_or_none()
            if not existing_appt:
                raise HTTPException(status_code=404, detail="Original appointment not found")

        # 4. Slot Validation (if not waitlist)
        if not payload.is_waitlist:
            available_slots = await get_available_slots(
                shop_id=1,
                service_duration_minutes=service.duration_minutes,
                date=start_time_naive.date(),
                db=db,
                exclude_appointment_id=payload.appointment_id
            )
            if not any(slot == start_time_naive for slot in available_slots):
                raise HTTPException(status_code=400, detail="Slot unavailable")

        # 5. Get/Create Client
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
                phone="unknown"
            )
            db.add(client)
            await db.flush()

        # 6. Create/Update Appointment
        end_time = start_time_naive + timedelta(minutes=service.duration_minutes)
        start_time_utc = start_time_naive.replace(tzinfo=tz.utc)
        end_time_utc = end_time.replace(tzinfo=tz.utc)

        status = AppointmentStatus.WAITLIST if payload.is_waitlist else (
            AppointmentStatus.CONFIRMED if payload.appointment_id else AppointmentStatus.NEW
        )

        tenant_stmt = select(Tenant).where(Tenant.id == tenant_id)
        tenant = (await db.execute(tenant_stmt)).scalar_one()
        shop = await get_tenant_shop(db, tenant)
        if not shop:
            raise HTTPException(status_code=400, detail="Shop not configured")

        if existing_appt:
            existing_appt.service_id = payload.service_id
            existing_appt.start_time = start_time_utc
            existing_appt.end_time = end_time_utc
            existing_appt.status = status
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
                status=status,
                car_make=payload.car_make,
                car_year=payload.car_year,
                vin=payload.vin
            )
            db.add(appt)

        await db.commit()
        await db.refresh(appt)

        # 7. Notifications
        from app.services.notification_service import NotificationService
        import asyncio

        time_str = start_time_naive.strftime('%d.%m.%Y %H:%M')
        
        async def notify():
            try:
                # Notify User
                msg = f"✅ <b>Запись подтверждена!</b>\n\n🔧 <b>Услуга:</b> {service.name}\n🕐 <b>Время:</b> {time_str}"
                if payload.is_waitlist:
                    msg = f"📝 <b>Лист ожидания</b>\n\n🔧 <b>Услуга:</b> {service.name}\n📅 <b>Дата:</b> {start_time_naive.strftime('%d.%m.%Y')}"
                
                await NotificationService.send_raw_message(payload.telegram_id, msg)

                # Notify Admin
                if not payload.is_waitlist:
                    admin_msg = f"🆕 <b>Новая запись! (WebApp)</b>\n\n👤 {payload.full_name}\n🔧 {service.name}\n🕐 {time_str}"
                    await NotificationService.notify_admin(admin_msg)
            except Exception as e:
                logger.error(f"Notification error: {e}")

        asyncio.create_task(notify())

        # 8. Redis Sync
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
                    "status": appt.status.value
                }
            }
            await redis.publish("appointments_updates", json.dumps(broadcast_message))
        except Exception as e:
            logger.error(f"Redis publish error: {e}")

        return appt

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Public booking error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
