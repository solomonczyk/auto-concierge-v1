"""
Demo Runner — creates demo client + appointment and runs status workflow.
Only allowed for tenant with slug="demo-service".
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone as tz
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.config import settings
from app.db.session import async_session_local, get_db
from app.models.models import (
    Appointment,
    AppointmentStatus,
    Client,
    Service,
    Shop,
    Tenant,
    TenantSettings,
)
from app.services.redis_service import RedisService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/demo", tags=["demo"])
logger = logging.getLogger(__name__)

DEMO_SLUG = "demo-service"


async def get_demo_tenant(
    tenant_id: int = Depends(deps.get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    stmt = select(Tenant).where(Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant or tenant.slug != DEMO_SLUG:
        raise HTTPException(
            status_code=403,
            detail="Demo mode allowed only for demo tenant",
        )
    return tenant


async def _move_status(
    appointment_id: int,
    new_status: str,
    tenant_id: int,
) -> None:
    """Update appointment status and publish to Redis (same as PATCH handler)."""
    async with async_session_local() as db:
        from sqlalchemy.orm import joinedload

        stmt = select(Appointment).options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
        ).where(
            Appointment.id == appointment_id,
            Appointment.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        appt = result.scalar_one_or_none()
        if not appt:
            logger.warning(f"Demo: appointment {appointment_id} not found")
            return

        old_status = appt.status
        appt.status = AppointmentStatus(new_status)
        await db.commit()
        await db.refresh(appt)

        if appt.status != old_status:
            chat_id = appt.client.telegram_id if appt.client.telegram_id and appt.client.telegram_id > 0 else settings.ADMIN_CHAT_ID
            if chat_id:
                try:
                await NotificationService.notify_client_status_change(
                    chat_id=chat_id,
                    service_name=appt.service.name,
                    new_status=appt.status.value,
                )
                except Exception as e:
                    logger.error(f"Demo notify error: {e}")

        redis = RedisService.get_redis()
        await redis.publish(
            f"appointments_updates:{tenant_id}",
            json.dumps({
                "type": "STATUS_UPDATE",
                "data": {
                    "id": appt.id,
                    "shop_id": appt.shop_id,
                    "status": appt.status,
                },
            }),
        )


async def _demo_workflow(appointment_id: int, tenant_id: int) -> None:
    await asyncio.sleep(5)
    await _move_status(appointment_id, "confirmed", tenant_id)
    await asyncio.sleep(5)
    await _move_status(appointment_id, "in_progress", tenant_id)
    await asyncio.sleep(5)
    await _move_status(appointment_id, "completed", tenant_id)


@router.post("/run")
async def run_demo(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_demo_tenant),
):
    tenant_id = tenant.id

    shop = (await db.execute(select(Shop).where(Shop.tenant_id == tenant_id).limit(1))).scalar_one_or_none()
    if not shop:
        raise HTTPException(status_code=400, detail="Demo tenant has no shop")

    service = (await db.execute(select(Service).where(Service.tenant_id == tenant_id).limit(1))).scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=400, detail="Demo tenant has no services")

    demo_tg_id = -(tenant_id * 1_000_001)

    existing = (await db.execute(
        select(Client).where(Client.telegram_id == demo_tg_id, Client.tenant_id == tenant_id)
    )).scalar_one_or_none()

    if existing:
        client = existing
    else:
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
        await db.flush()

    tz_name = settings.SHOP_TIMEZONE
    try:
        ts = (await db.execute(select(TenantSettings).where(TenantSettings.tenant_id == tenant_id))).scalar_one_or_none()
        if ts and ts.timezone:
            tz_name = ts.timezone
    except Exception:
        pass
    shop_tz = ZoneInfo(tz_name)
    now_local = datetime.now(shop_tz)
    tomorrow = (now_local.date() + timedelta(days=1))
    start_local = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
    start_utc = start_local.astimezone(tz.utc)
    end_utc = start_utc + timedelta(minutes=service.duration_minutes)

    appointment = Appointment(
        tenant_id=tenant_id,
        shop_id=shop.id,
        client_id=client.id,
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
        json.dumps({
            "type": "NEW_APPOINTMENT",
            "data": {
                "id": appointment.id,
                "shop_id": appointment.shop_id,
                "start_time": appointment.start_time.isoformat(),
                "status": appointment.status.value,
            },
        }),
    )

    asyncio.create_task(_demo_workflow(appointment.id, tenant_id))

    return {"status": "demo_started"}
