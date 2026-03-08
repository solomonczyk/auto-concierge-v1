from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone as tz
from zoneinfo import ZoneInfo
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import joinedload, selectinload
from app.db.session import get_db
from app.api import deps
from app.models.models import Appointment, AppointmentHistory, AppointmentStatus, Client, IntegrationStatus, Service, User, UserRole, Tenant, TariffPlan, TenantSettings
from app.models.auto_extensions import ClientAutoProfile, AppointmentAutoSnapshot
from app.services.redis_service import RedisService 
from app.services.external_integration_service import external_integration
from app.core.config import settings
from app.core.slots import get_available_slots
from app.core.metrics import (
    APPOINTMENTS_CREATED_TOTAL,
    APPOINTMENTS_CREATION_FAILED_TOTAL,
    APPOINTMENTS_EXTERNAL_SYNC_FAILED_TOTAL,
    APPOINTMENT_STATUS_TRANSITIONS_TOTAL,
)
from app.bot.tenant import get_tenant_shop
from app.schemas.appointment_history import AppointmentHistoryRead
from app.services.usage_service import check_appointments_limit, LimitExceededError
from app.services.audit_service import log_audit
from app.services.outbox_service import enqueue_appointment_created_event
from app.services.appointment_integration_service import run_appointment_integration_sync
from app.core.rate_limit import PUBLIC_BOOKING_RATE_LIMIT, limiter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Exclude soft-deleted from normal queries
_NOT_DELETED = Appointment.deleted_at.is_(None)
_CLIENT_NOT_DELETED = Client.deleted_at.is_(None)
router = APIRouter()


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


def _upsert_appointment_auto_snapshot(
    db: AsyncSession,
    appt: Appointment,
    car_make: Optional[str],
    car_year: Optional[int],
    vin: Optional[str],
) -> None:
    """Create or update AppointmentAutoSnapshot. Skips if all fields are None."""
    if car_make is None and car_year is None and vin is None:
        return
    sn = getattr(appt, "auto_snapshot", None)
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
    timezone: Optional[str] = None  # e.g. Europe/Moscow, from Intl.DateTimeFormat().resolvedOptions().timeZone

class AppointmentCreate(BaseModel):
    service_id: int
    start_time: datetime
    # client info (simplified for MVP: creating client on fly or linking)
    client_name: str
    client_phone: str
    client_telegram_id: int = None

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


class AppointmentAutoInfo(BaseModel):
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None


class AppointmentRead(BaseModel):
    id: int
    shop_id: int
    service_id: int
    client_id: int
    start_time: datetime
    end_time: datetime
    status: str
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None
    auto_info: Optional[AppointmentAutoInfo] = None
    integration_status: Optional[str] = None
    last_integration_error: Optional[str] = None
    last_integration_attempt_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    client: Optional[ClientShort] = None
    service: Optional[ServiceShort] = None

    class Config:
        from_attributes = True


class KanbanBoardResponse(BaseModel):
    """Kanban board grouped by status. Terminal statuses (cancelled, no_show) excluded."""
    waitlist: List[AppointmentRead] = []
    new: List[AppointmentRead] = []
    confirmed: List[AppointmentRead] = []
    in_progress: List[AppointmentRead] = []
    completed: List[AppointmentRead] = []

from pydantic import BaseModel, field_validator

class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus
    reason: Optional[str] = None

    @field_validator("status", mode="before")
    @classmethod
    def lowercase_status(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower()
        return v

class AppointmentUpdate(BaseModel):
    service_id: Optional[int] = None
    start_time: Optional[datetime] = None
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None


@router.patch("/{id}", response_model=AppointmentRead)
async def update_appointment(
    id: int,
    appt_update: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
    current_user: User = Depends(deps.get_current_active_user),
):
    stmt = select(Appointment).options(
        selectinload(Appointment.auto_snapshot)
    ).where(
        and_(Appointment.id == id, Appointment.tenant_id == tenant_id, _NOT_DELETED)
    )
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

    _upsert_appointment_auto_snapshot(
        db, appt,
        appt_update.car_make,
        appt_update.car_year,
        appt_update.vin,
    )

    await db.commit()
    
    # Re-fetch with relations to avoid lazy load errors in response validation
    try:
        stmt = select(Appointment).options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
        ).where(Appointment.id == id)
        result = await db.execute(stmt)
        refreshed_appt = result.scalar_one_or_none()
        if refreshed_appt is not None:
            appt = refreshed_appt
        else:
            logger.warning(
                "Appointment patch reread failed after commit, returning in-memory appointment id=%s tenant_id=%s",
                id,
                tenant_id,
            )
    except Exception as reread_error:
        logger.error(
            "Appointment patch reread errored after commit appointment_id=%s tenant_id=%s: %s",
            id,
            tenant_id,
            reread_error,
        )

    try:
        await log_audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=current_user.id,
            action="update",
            entity_type="appointment",
            entity_id=str(appt.id),
            payload_after={"id": appt.id, "service_id": appt.service_id, "start_time": appt.start_time.isoformat()},
            source="dashboard",
        )
        await db.commit()
    except Exception as audit_error:
        await db.rollback()
        logger.error(
            "Appointment patch audit commit failed after update appointment_id=%s tenant_id=%s: %s",
            appt.id,
            tenant_id,
            audit_error,
        )

    # Broadcast update
    try:
        redis = RedisService.get_redis()
        message = {
            "type": "APPOINTMENT_UPDATED",
            "data": {
                "id": appt.id,
                "shop_id": appt.shop_id
            }
        }
        await redis.publish(f"appointments_updates:{tenant_id}", json.dumps(message))
    except Exception as redis_error:
        logger.error(
            "Appointment patch redis publish failed appointment_id=%s tenant_id=%s: %s",
            appt.id,
            tenant_id,
            redis_error,
        )
    _enrich_appointment_auto_fields(appt)
    return appt

@router.post("/", response_model=AppointmentRead)
async def create_appointment(
    appt: AppointmentCreate, 
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
    current_user: User = Depends(deps.require_role([UserRole.ADMIN, UserRole.MANAGER]))
):
    # 0. Enforce Tenancy and SaaS Limits
    shop_id = current_user.shop_id

    stmt_tenant = select(Tenant).options(joinedload(Tenant.tariff_plan)).where(Tenant.id == tenant_id)
    tenant = (await db.execute(stmt_tenant)).scalar_one()
    plan_name = tenant.tariff_plan.name if tenant.tariff_plan else None

    try:
        await check_appointments_limit(db, tenant_id, plan_name)
    except LimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.to_detail(),
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
                Appointment.deleted_at.is_(None),
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

        stmt = select(Client).where(
            and_(
                Client.phone == appt.client_phone,
                Client.tenant_id == tenant_id,
                Client.deleted_at.is_(None),
            )
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()
        client_created = False
        if not client:
            client_created = True
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
            status=AppointmentStatus.NEW,
            integration_status=IntegrationStatus.PENDING,
        )
        
        db.add(new_appt)
        await db.commit()
        
        # Re-fetch with relations to avoid lazy load errors in response validation
        final_appt = new_appt
        try:
            stmt = select(Appointment).options(
                joinedload(Appointment.client),
                joinedload(Appointment.service),
                selectinload(Appointment.auto_snapshot),
            ).where(Appointment.id == new_appt.id)
            result = await db.execute(stmt)
            refreshed_appt = result.scalar_one_or_none()
            if refreshed_appt is not None:
                final_appt = refreshed_appt
            else:
                logger.warning(
                    "Appointment create reread failed after commit, returning in-memory appointment id=%s tenant_id=%s",
                    new_appt.id,
                    tenant_id,
                )
                final_appt.client = client
                final_appt.service = service
        except Exception as reread_error:
            logger.error(
                "Appointment create reread errored after commit appointment_id=%s tenant_id=%s: %s",
                new_appt.id,
                tenant_id,
                reread_error,
            )
            final_appt.client = client
            final_appt.service = service
        
        from app.models.models import AppointmentHistory

        try:
            db.add(AppointmentHistory(
                appointment_id=final_appt.id,
                tenant_id=tenant_id,
                old_status="",
                new_status=AppointmentStatus.NEW.value,
                changed_by_user_id=current_user.id,
                source="dashboard",
            ))
            await log_audit(
                db,
                tenant_id=tenant_id,
                actor_user_id=current_user.id,
                action="create",
                entity_type="appointment",
                entity_id=str(final_appt.id),
                payload_after={"id": final_appt.id, "status": "new", "start_time": final_appt.start_time.isoformat()},
                source="dashboard",
            )
            if client_created:
                await log_audit(
                    db,
                    tenant_id=tenant_id,
                    actor_user_id=current_user.id,
                    action="create",
                    entity_type="client",
                    entity_id=str(client.id),
                    payload_after={"id": client.id, "full_name": client.full_name, "phone": client.phone},
                    source="dashboard",
                )
            await enqueue_appointment_created_event(
                db,
                tenant_id=tenant_id,
                appointment_id=final_appt.id,
            )
            await db.commit()
        except Exception as history_audit_error:
            await db.rollback()
            logger.error(
                "Appointment create history/audit commit failed after create appointment_id=%s tenant_id=%s: %s",
                final_appt.id,
                tenant_id,
                history_audit_error,
            )

        APPOINTMENTS_CREATED_TOTAL.labels(
            tenant_id=str(tenant_id), source="dashboard"
        ).inc()

        try:
            redis_pub = RedisService.get_redis()
            ws_msg = {
                "type": "appointment_created",
                "data": {
                    "id": final_appt.id,
                    "shop_id": final_appt.shop_id,
                    "status": final_appt.status.value,
                },
            }
            await redis_pub.publish(
                f"appointments_updates:{tenant_id}", json.dumps(ws_msg)
            )
        except Exception:
            pass

        _enrich_appointment_auto_fields(final_appt)
        return final_appt
        
    finally:
        await redis.delete(lock_key)

@router.patch("/{appointment_id}/status", response_model=AppointmentRead)
async def update_appointment_status(
    appointment_id: int,
    status_update: AppointmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Change appointment status. Used by Kanban for moving cards.
    Validates transitions via state machine, writes history, publishes WS event.
    """
    from app.services.appointment_state_machine import validate_transition, TransitionError
    from app.models.models import AppointmentHistory

    stmt = select(Appointment).options(
        joinedload(Appointment.client),
        joinedload(Appointment.service),
        selectinload(Appointment.auto_snapshot),
    ).where(and_(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id, _NOT_DELETED))

    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()

    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    old_status = appt.status
    target = status_update.status

    try:
        validate_transition(
            current=old_status,
            target=target,
            role=current_user.role,
        )
    except TransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        )

    appt.status = target
    if target == AppointmentStatus.COMPLETED:
        appt.completed_at = datetime.now(tz.utc)
    elif old_status == AppointmentStatus.COMPLETED:
        appt.completed_at = None

    reason = None
    if target in (AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW) and status_update.reason:
        reason = status_update.reason

    db.add(AppointmentHistory(
        appointment_id=appt.id,
        tenant_id=tenant_id,
        old_status=old_status.value,
        new_status=target.value,
        changed_by_user_id=current_user.id,
        source="api",
        reason=reason,
    ))

    await db.commit()

    try:
        refreshed_stmt = select(Appointment).options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
        ).where(and_(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id, _NOT_DELETED))
        refreshed_result = await db.execute(refreshed_stmt)
        refreshed_appt = refreshed_result.scalar_one_or_none()
        if refreshed_appt is not None:
            appt = refreshed_appt
        else:
            logger.warning(
                "Appointment status update reread failed after commit, returning in-memory appointment id=%s tenant_id=%s",
                appointment_id,
                tenant_id,
            )
    except Exception as reread_error:
        logger.error(
            "Appointment status update reread errored after commit appointment_id=%s tenant_id=%s: %s",
            appointment_id,
            tenant_id,
            reread_error,
        )

    try:
        integration_appt = await run_appointment_integration_sync(
            db=db,
            appointment_id=appt.id,
            tenant_id=tenant_id,
        )
        if integration_appt is not None:
            appt = integration_appt
    except Exception as integration_error:
        logger.error(
            "Appointment status update integration sync failed after commit appointment_id=%s tenant_id=%s: %s",
            appt.id,
            tenant_id,
            integration_error,
        )

    from app.services.notification_service import NotificationService, STATUS_TO_NOTIFICATION_EVENT

    notification_event = STATUS_TO_NOTIFICATION_EVENT.get(target.value)
    if notification_event and appt.client and appt.client.telegram_id:
        import asyncio

        async def notify_via_dispatch():
            try:
                await NotificationService.dispatch(
                    event_type=notification_event,
                    appointment_id=appt.id,
                    tenant_id=tenant_id,
                    recipient_roles=["client"],
                    recipient_ids={"client_telegram_id": appt.client.telegram_id},
                    context={
                        "old_status": old_status.value,
                        "new_status": target.value,
                        "service_name": appt.service.name if appt.service else None,
                    },
                )
            except NotImplementedError:
                logger.warning(
                    "NotificationService.dispatch not wired yet for appointment %s",
                    appt.id,
                )
            except Exception as exc:
                logger.exception(
                    "Notification failed for appointment %s: %s",
                    appt.id,
                    exc,
                )

        asyncio.create_task(notify_via_dispatch())

    try:
        redis = RedisService.get_redis()
        payload = {
            "type": "appointment_status_updated",
            "appointment_id": appt.id,
            "old_status": old_status.value,
            "new_status": target.value,
        }
        await redis.publish(f"appointments_updates:{tenant_id}", json.dumps(payload))
    except Exception as redis_error:
        logger.error(
            "Appointment status update redis publish failed appointment_id=%s tenant_id=%s: %s",
            appt.id,
            tenant_id,
            redis_error,
        )

    APPOINTMENT_STATUS_TRANSITIONS_TOTAL.labels(
        tenant_id=str(tenant_id),
        old_status=old_status.value,
        new_status=target.value,
    ).inc()

    _enrich_appointment_auto_fields(appt)
    return appt

def _should_show_completed_in_kanban(
    completed_at: Optional[datetime],
    work_end: int,
    tz_name: str,
) -> bool:
    """
    Show in 'Готова' column:
    - Working day (Mon–Fri): only if completed today and before work_end.
    - Weekend (Sat–Sun): show if completed during this weekend; cards stay until next working day.
    """
    if completed_at is None:
        return False
    tz_obj = ZoneInfo(tz_name)
    now_local = datetime.now(tz_obj)
    completed_local = completed_at.astimezone(tz_obj)
    now_weekday = now_local.weekday()  # Mon=0, Sun=6

    # Weekend (Sat=5, Sun=6): show completed from this weekend until next working day
    if now_weekday >= 5:
        # Same weekend: completed on Sat or Sun of current week
        completed_weekday = completed_local.weekday()
        if completed_weekday >= 5:
            # Both on weekend; same weekend = completed within last 2 days
            return (now_local - completed_local).days <= 2
        # Completed on a working day (e.g. Friday) but we're on weekend — show if since last workday end
        days_to_friday = now_weekday - 4  # Sat: 1, Sun: 2
        last_friday = now_local - timedelta(days=days_to_friday)
        weekend_start = last_friday.replace(hour=work_end, minute=0, second=0, microsecond=0)
        return completed_local >= weekend_start

    # Working day: show if completed today and before work_end
    if completed_local.date() != now_local.date():
        return False
    end_of_day = now_local.replace(hour=work_end, minute=0, second=0, microsecond=0)
    return now_local < end_of_day


@router.get("/", response_model=List[AppointmentRead])
async def read_appointments(
    skip: int = 0,
    limit: int = 100,
    for_kanban: bool = False,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
):
    fetch_limit = limit * 3 if for_kanban else limit
    stmt = (
        select(Appointment)
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
        )
        .where(and_(Appointment.tenant_id == tenant_id, _NOT_DELETED))
        .offset(skip)
        .limit(fetch_limit)
    )
    result = await db.execute(stmt)
    appointments = list(result.scalars().all())
    for a in appointments:
        _enrich_appointment_auto_fields(a)

    if for_kanban:
        ts_stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
        ts_result = await db.execute(ts_stmt)
        ts = ts_result.scalar_one_or_none()
        work_end = ts.work_end if ts else settings.WORK_END
        tz_name = ts.timezone if (ts and ts.timezone) else settings.SHOP_TIMEZONE
        appointments = [
            a for a in appointments
            if a.status != AppointmentStatus.COMPLETED
            or _should_show_completed_in_kanban(a.completed_at, work_end, tz_name)
        ]
        appointments = appointments[:limit]

    return appointments

KANBAN_STATUSES = (
    AppointmentStatus.WAITLIST,
    AppointmentStatus.NEW,
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.IN_PROGRESS,
    AppointmentStatus.COMPLETED,
)


@router.get("/today", response_model=List[AppointmentRead])
async def read_appointments_today(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
):
    """
    Today's appointments: only records for the current day in tenant timezone.
    Sorted by start_time ASC, paginated.
    """
    ts_stmt = select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    ts_result = await db.execute(ts_stmt)
    ts = ts_result.scalar_one_or_none()
    tz_name = ts.timezone if (ts and ts.timezone) else settings.SHOP_TIMEZONE
    tz_obj = ZoneInfo(tz_name)
    now_local = datetime.now(tz_obj)
    day_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end_local = day_start_local + timedelta(days=1)
    day_start_utc = day_start_local.astimezone(tz.utc)
    day_end_utc = day_end_local.astimezone(tz.utc)

    stmt = (
        select(Appointment)
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
        )
        .where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.start_time >= day_start_utc,
                Appointment.start_time < day_end_utc,
                _NOT_DELETED,
            )
        )
        .order_by(Appointment.start_time.asc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    appointments = list(result.scalars().all())
    for a in appointments:
        _enrich_appointment_auto_fields(a)
    return appointments


@router.get("/terminal", response_model=List[AppointmentRead])
async def read_appointments_terminal(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
):
    """
    Terminal block: only cancelled and no_show appointments.
    Paginated, tenant-scoped.
    """
    stmt = (
        select(Appointment)
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
        )
        .where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.status.in_(
                    (
                        AppointmentStatus.CANCELLED,
                        AppointmentStatus.NO_SHOW,
                    )
                ),
                _NOT_DELETED,
            )
        )
        .order_by(Appointment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    appointments = list(result.scalars().all())
    for a in appointments:
        _enrich_appointment_auto_fields(a)
    return appointments


@router.get("/kanban", response_model=KanbanBoardResponse)
async def read_appointments_kanban(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
):
    """
    Kanban board for operator dashboard. Grouped by status:
    waitlist, new, confirmed, in_progress, completed.
    Excludes terminal statuses: cancelled, no_show.
    Sorted by start_time ASC within each column.
    """
    stmt = (
        select(Appointment)
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
        )
        .where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.status.in_(KANBAN_STATUSES),
                _NOT_DELETED,
            )
        )
        .order_by(Appointment.start_time.asc())
    )
    result = await db.execute(stmt)
    appointments = list(result.scalars().all())
    for a in appointments:
        _enrich_appointment_auto_fields(a)

    groups: Dict[str, List] = {
        "waitlist": [],
        "new": [],
        "confirmed": [],
        "in_progress": [],
        "completed": [],
    }
    for a in appointments:
        key = a.status.value
        if key in groups:
            groups[key].append(a)

    return KanbanBoardResponse(**groups)


@router.get("/{appointment_id}/history", response_model=List[AppointmentHistoryRead])
async def read_appointment_history(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
):
    """
    Get status change history for an appointment (lifecycle audit).
    Returns records ordered by created_at ASC.
    """
    stmt = (
        select(AppointmentHistory, User.username)
        .outerjoin(User, AppointmentHistory.changed_by_user_id == User.id)
        .where(
            and_(
                AppointmentHistory.appointment_id == appointment_id,
                AppointmentHistory.tenant_id == tenant_id,
            )
        )
        .order_by(AppointmentHistory.created_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    appt_stmt = select(Appointment).where(
        and_(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id, _NOT_DELETED)
    )
    appt_result = await db.execute(appt_stmt)
    if not appt_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Appointment not found")

    return [
        AppointmentHistoryRead(
            id=h.id,
            appointment_id=h.appointment_id,
            old_status=h.old_status,
            new_status=h.new_status,
            created_at=h.created_at,
            actor=username,
        )
        for h, username in rows
    ]


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def read_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
):
    """
    Get appointment by ID. Requires authentication.
    Only returns appointments belonging to the current tenant.
    """
    stmt = (
        select(Appointment)
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
        )
        .where(and_(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id, _NOT_DELETED))
    )
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()
    
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enrich_appointment_auto_fields(appt)
    return appt


@router.put("/{appointment_id}", response_model=AppointmentRead)
async def put_appointment(
    appointment_id: int,
    appt_update: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
):
    """
    Update appointment by ID. Only within tenant scope.
    Updates only allowed fields: service_id, start_time, car_make, car_year, vin.
    Returns 404 if not found or belongs to another tenant.
    """
    stmt = select(Appointment).options(
        selectinload(Appointment.auto_snapshot),
    ).where(
        and_(
            Appointment.id == appointment_id,
            Appointment.tenant_id == tenant_id,
            _NOT_DELETED,
        )
    )
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt_update.service_id is not None:
        service = await db.get(Service, appt_update.service_id)
        if not service or service.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Service not found")
        appt.service_id = appt_update.service_id
        start = appt_update.start_time or appt.start_time
        appt.end_time = start + timedelta(minutes=service.duration_minutes)

    if appt_update.start_time is not None:
        new_start = appt_update.start_time
        if new_start.tzinfo is None:
            new_start = new_start.replace(tzinfo=tz.utc)
        else:
            new_start = new_start.astimezone(tz.utc)
        new_start_naive = new_start.replace(tzinfo=None)

        service = await db.get(Service, appt.service_id)
        available_slots = await get_available_slots(
            shop_id=appt.shop_id,
            service_duration_minutes=service.duration_minutes,
            date=new_start_naive.date(),
            db=db,
            exclude_appointment_id=appointment_id,
        )
        if not any(
            slot == new_start or slot.replace(tzinfo=None) == new_start_naive
            for slot in available_slots
        ):
            raise HTTPException(
                status_code=400,
                detail="Selected time is outside working hours or conflicts with another appointment",
            )

        appt.start_time = appt_update.start_time
        appt.end_time = appt.start_time + timedelta(minutes=service.duration_minutes)

    _upsert_appointment_auto_snapshot(
        db, appt,
        appt_update.car_make,
        appt_update.car_year,
        appt_update.vin,
    )

    await db.commit()

    stmt = select(Appointment).options(
        joinedload(Appointment.client),
        joinedload(Appointment.service),
        selectinload(Appointment.auto_snapshot),
    ).where(and_(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id))
    result = await db.execute(stmt)
    refreshed_appt = result.scalar_one_or_none()
    if refreshed_appt is not None:
        appt = refreshed_appt
    else:
        logger.warning(
            "Appointment update reread failed after commit, returning in-memory appointment id=%s tenant_id=%s",
            appointment_id,
            tenant_id,
        )

    integration_appt = await run_appointment_integration_sync(
        db=db,
        appointment_id=appt.id,
        tenant_id=tenant_id,
    )
    stmt = select(Appointment).options(
        joinedload(Appointment.client),
        joinedload(Appointment.service),
        selectinload(Appointment.auto_snapshot),
    ).where(and_(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id))
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none() or integration_appt

    try:
        redis = RedisService.get_redis()
        message = {
            "type": "APPOINTMENT_UPDATED",
            "data": {"id": appt.id, "shop_id": appt.shop_id},
        }
        await redis.publish(f"appointments_updates:{tenant_id}", json.dumps(message))
    except Exception as redis_error:
        logger.error(
            "Appointment update redis publish failed appointment_id=%s tenant_id=%s: %s",
            appt.id,
            tenant_id,
            redis_error,
        )
    _enrich_appointment_auto_fields(appt)
    return appt


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Soft-delete appointment by ID. Only within tenant scope.
    Sets deleted_at, deleted_by. Returns 204 No Content on success.
    """
    stmt = select(Appointment).where(
        and_(
            Appointment.id == appointment_id,
            Appointment.tenant_id == tenant_id,
            _NOT_DELETED,
        )
    )
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    payload_before = {"id": appt.id, "status": appt.status.value, "start_time": appt.start_time.isoformat()}
    appt.deleted_at = datetime.now(tz.utc)
    appt.deleted_by = current_user.id
    await log_audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=current_user.id,
        action="soft_delete",
        entity_type="appointment",
        entity_id=str(appt.id),
        payload_before=payload_before,
        payload_after=None,
        source="dashboard",
    )
    await db.commit()


@router.post("/public", response_model=AppointmentRead)
@limiter.limit(PUBLIC_BOOKING_RATE_LIMIT)
async def create_public_appointment(
    request: Request,
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
            stmt = select(Appointment).options(
                selectinload(Appointment.auto_snapshot),
            ).where(
                and_(Appointment.id == payload.appointment_id, Appointment.tenant_id == tenant_id)
            )
            result = await db.execute(stmt)
            existing_appt = result.scalar_one_or_none()
            if not existing_appt:
                raise HTTPException(status_code=404, detail="Исходная запись не найдена")

        # 5. Slot Validation (if not waitlist)
        if not payload.is_waitlist:
            available_slots = await get_available_slots(
                shop_id=shop.id,
                service_duration_minutes=service.duration_minutes,
                date=start_time_naive.date(),
                db=db,
                exclude_appointment_id=payload.appointment_id
            )
            if not any(
                slot == start_time
                or slot.replace(tzinfo=None) == start_time_naive
                for slot in available_slots
            ):
                raise HTTPException(status_code=400, detail="Выбранное время уже занято")

        # 6. Get/Create Client
        stmt = (
            select(Client)
            .where(and_(Client.telegram_id == payload.telegram_id, Client.tenant_id == tenant_id))
            .options(selectinload(Client.auto_profile))
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()

        if not client:
            client = Client(
                tenant_id=tenant_id,
                telegram_id=payload.telegram_id,
                full_name=payload.full_name,
                phone="unknown",
            )
            db.add(client)
            await db.flush()
            if payload.car_make or payload.car_year or payload.vin:
                profile = ClientAutoProfile(
                    client_id=client.id,
                    car_make=payload.car_make,
                    car_year=payload.car_year,
                    vin=payload.vin,
                )
                db.add(profile)
        else:
            if payload.car_make or payload.car_year or payload.vin:
                if client.auto_profile:
                    if payload.car_make is not None:
                        client.auto_profile.car_make = payload.car_make
                    if payload.car_year is not None:
                        client.auto_profile.car_year = payload.car_year
                    if payload.vin is not None:
                        client.auto_profile.vin = payload.vin
                else:
                    profile = ClientAutoProfile(
                        client_id=client.id,
                        car_make=payload.car_make,
                        car_year=payload.car_year,
                        vin=payload.vin,
                    )
                    db.add(profile)
            if client.full_name == "Guest" and payload.full_name:
                client.full_name = payload.full_name

        # 7. Create/Update Appointment with Collision Protection
        end_time_naive = start_time_naive + timedelta(minutes=service.duration_minutes)
        start_time_utc = start_time
        end_time_utc = end_time_naive.replace(tzinfo=tz.utc)

        # Collision Check immediately before booking
        if not payload.is_waitlist:
            # Race condition protection (Soft Lock)
            redis = RedisService.get_redis()
            lock_key = f"booking_lock:{shop.id}:{start_time_utc.isoformat()}"
            is_locked = await redis.set(lock_key, "1", nx=True, ex=10)
            if not is_locked:
                 raise HTTPException(
                    status_code=409,
                    detail="Это время сейчас бронируется. Попробуйте еще раз"
                )
            
            try:
                stmt_collide = select(Appointment).where(
                    and_(
                        Appointment.shop_id == shop.id,
                        Appointment.status != AppointmentStatus.CANCELLED,
                        Appointment.status != AppointmentStatus.WAITLIST,
                        Appointment.start_time < end_time_utc,
                        Appointment.end_time > start_time_utc
                    )
                )
                if payload.appointment_id:
                    stmt_collide = stmt_collide.where(Appointment.id != payload.appointment_id)
                
                res_collide = await db.execute(stmt_collide)
                if res_collide.scalars().first():
                    raise HTTPException(status_code=409, detail="Это время уже занято")
            finally:
                if not payload.appointment_id: # Only lock for new bookings to avoid complex re-locks for now
                    await redis.delete(lock_key)

        status = AppointmentStatus.WAITLIST if payload.is_waitlist else (
            AppointmentStatus.CONFIRMED if payload.appointment_id else AppointmentStatus.NEW
        )

        if existing_appt:
            existing_appt.service_id = payload.service_id
            existing_appt.start_time = start_time_utc
            existing_appt.end_time = end_time_utc
            existing_appt.status = status
            _upsert_appointment_auto_snapshot(
                db, existing_appt,
                payload.car_make,
                payload.car_year,
                payload.vin,
            )
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
            )
            db.add(appt)
            await db.flush()
            _upsert_appointment_auto_snapshot(
                db, appt,
                payload.car_make,
                payload.car_year,
                payload.vin,
            )

        await db.commit()
        
        # Re-fetch with relations to avoid lazy load errors in response validation
        stmt = select(Appointment).options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            selectinload(Appointment.auto_snapshot),
        ).where(and_(Appointment.id == appt.id, Appointment.tenant_id == tenant_id))
        result = await db.execute(stmt)
        appt = result.scalar_one()

        APPOINTMENTS_CREATED_TOTAL.labels(
            tenant_id=str(tenant_id), source="public"
        ).inc()

        from app.services.notification_service import NotificationService
        import asyncio

        # Format in user's timezone so bot message matches WebApp display
        display_tz = payload.timezone or settings.SHOP_TIMEZONE
        try:
            tz_obj = ZoneInfo(display_tz)
            local_time = start_time.astimezone(tz_obj)
        except Exception:
            local_time = start_time
        time_str = local_time.strftime('%d.%m.%Y %H:%M')
        
        async def notify():
            try:
                recipient_roles = ["client"]
                if not payload.is_waitlist and settings.ADMIN_CHAT_ID and str(settings.ADMIN_CHAT_ID) != str(payload.telegram_id):
                    recipient_roles.append("manager")
                recipient_ids = {"client_telegram_id": payload.telegram_id}
                if settings.ADMIN_CHAT_ID:
                    recipient_ids["manager_chat_id"] = settings.ADMIN_CHAT_ID
                await NotificationService.dispatch(
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
            await redis.publish(f"appointments_updates:{tenant_id}", json.dumps(broadcast_message))
        except Exception as e:
            logger.error(f"Redis publish error: {e}")

        _enrich_appointment_auto_fields(appt)
        return appt

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Public booking error: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервиса")
