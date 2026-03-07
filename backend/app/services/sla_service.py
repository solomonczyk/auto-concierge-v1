"""SLA timers: auto-transitions and reminders.

Designed to be called periodically by APScheduler or a cron-like task.
"""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Appointment,
    AppointmentHistory,
    AppointmentStatus,
    TenantSettings,
)
from app.services.appointment_state_machine import validate_transition, TransitionError

logger = logging.getLogger(__name__)

CONFIRMATION_TIMEOUT_MINUTES = 15


async def check_unconfirmed_appointments(db: AsyncSession) -> list[int]:
    """Find NEW appointments older than CONFIRMATION_TIMEOUT_MINUTES.

    Returns list of appointment IDs that need manager attention.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=CONFIRMATION_TIMEOUT_MINUTES)
    stmt = select(Appointment).where(
        and_(
            Appointment.status == AppointmentStatus.NEW,
            Appointment.created_at <= cutoff,
        )
    )
    result = await db.execute(stmt)
    overdue = list(result.scalars().all())

    ids = [a.id for a in overdue]
    if ids:
        logger.warning(
            "sla.unconfirmed_timeout count=%d ids=%s",
            len(ids),
            ids[:10],
            extra={"event_type": "sla_warning", "count": len(ids)},
        )
    return ids


async def auto_no_show(db: AsyncSession) -> int:
    """Mark CONFIRMED appointments as NO_SHOW if start_time has passed.

    Returns number of transitioned appointments.
    """
    now = datetime.now(timezone.utc)
    stmt = select(Appointment).where(
        and_(
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.start_time < now,
        )
    )
    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    transitioned = 0
    for appt in candidates:
        try:
            validate_transition(
                current=appt.status,
                target=AppointmentStatus.NO_SHOW,
                is_system=True,
            )
        except TransitionError:
            continue

        old = appt.status
        appt.status = AppointmentStatus.NO_SHOW

        db.add(AppointmentHistory(
            appointment_id=appt.id,
            tenant_id=appt.tenant_id,
            old_status=old.value,
            new_status=AppointmentStatus.NO_SHOW.value,
            changed_by_user_id=None,
            source="system_sla",
        ))
        transitioned += 1

    if transitioned:
        await db.commit()
        logger.info(
            "sla.auto_no_show count=%d",
            transitioned,
            extra={"event_type": "sla_action", "count": transitioned},
        )

    return transitioned
