"""SLA alerts API for dashboard."""

from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api import deps
from app.db.session import get_db
from app.models.models import Appointment, AppointmentStatus
from app.services.sla_service import CONFIRMATION_TIMEOUT_MINUTES

router = APIRouter()


class UnconfirmedAppointmentOut(BaseModel):
    appointment_id: int
    client_name: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/unconfirmed", response_model=List[UnconfirmedAppointmentOut])
async def get_unconfirmed_sla_alerts(
    minutes: int = CONFIRMATION_TIMEOUT_MINUTES,
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(deps.get_current_tenant_id),
):
    """
    SLA alerts: NEW appointments created more than N minutes ago.
    For dashboard SLA alerts panel.
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    stmt = (
        select(Appointment)
        .options(joinedload(Appointment.client))
        .where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.status == AppointmentStatus.NEW,
                Appointment.created_at < cutoff_time,
            )
        )
        .order_by(Appointment.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    appointments = result.unique().scalars().all()

    return [
        UnconfirmedAppointmentOut(
            appointment_id=a.id,
            client_name=a.client.full_name if a.client else "—",
            created_at=a.created_at,
        )
        for a in appointments
    ]
