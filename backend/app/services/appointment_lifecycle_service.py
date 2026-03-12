"""
Appointment lifecycle actions service.

Cancel and reschedule are canonical lifecycle actions. All future flows
(Telegram WebApp, operator dashboard, reminders, self-service) must use this
service or its HTTP endpoint — do not scatter logic elsewhere.

Contract: see docs/APPOINTMENT_LIFECYCLE.md
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.models import Appointment, AppointmentHistory, AppointmentStatus
from app.services.appointment_snapshot_service import get_appointment_snapshot
from app.schemas.appointment_snapshot import AppointmentSnapshotResponse


CancelResult = tuple[AppointmentSnapshotResponse, bool, str | None]
""" (snapshot, transitioned, old_status). old_status set only when transitioned. """


# Statuses that cannot be cancelled
CANCEL_FORBIDDEN_STATUSES = frozenset({
    AppointmentStatus.COMPLETED,
    AppointmentStatus.NO_SHOW,
})


class CancelForbiddenError(Exception):
    """Appointment cannot be cancelled (COMPLETED or NO_SHOW)."""
    pass


class AppointmentNotFoundError(Exception):
    """Appointment not found or belongs to another tenant."""
    pass


class RescheduleForbiddenError(Exception):
    """Appointment cannot be rescheduled (COMPLETED, NO_SHOW, CANCELLED)."""
    pass


class RescheduleSlotConflictError(Exception):
    """Target slot overlaps with another appointment."""
    pass


class RescheduleValidationError(Exception):
    """Invalid time range (new_start_time >= new_end_time)."""
    pass


# Statuses that cannot be rescheduled
RESCHEDULE_FORBIDDEN_STATUSES = frozenset({
    AppointmentStatus.COMPLETED,
    AppointmentStatus.NO_SHOW,
    AppointmentStatus.CANCELLED,
})


RescheduleResult = tuple[AppointmentSnapshotResponse, bool, datetime, datetime]
""" (snapshot, rescheduled, old_start_time, old_end_time). """


async def cancel_appointment(
    db: AsyncSession,
    appointment_id: int,
    tenant_id: int,
    *,
    changed_by_user_id: int | None = None,
    source: str = "api",
    reason: str | None = None,
) -> CancelResult:
    """
    Cancel appointment. Idempotent if already CANCELLED.

    Rules:
    - COMPLETED, NO_SHOW → CancelForbiddenError
    - CANCELLED → idempotent, returns current snapshot
    - Other statuses → transition to CANCELLED, write history

    Returns (snapshot, transitioned). Raises AppointmentNotFoundError if not found / wrong tenant.
    """
    stmt = (
        select(Appointment)
        .where(
            Appointment.id == appointment_id,
            Appointment.tenant_id == tenant_id,
            Appointment.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()

    if not appt:
        raise AppointmentNotFoundError()

    if appt.status in CANCEL_FORBIDDEN_STATUSES:
        raise CancelForbiddenError(
            f"Cannot cancel appointment in status '{appt.status.value}'"
        )

    if appt.status == AppointmentStatus.CANCELLED:
        snapshot = await get_appointment_snapshot(db, appointment_id, tenant_id)
        if snapshot is None:
            raise AppointmentNotFoundError()
        return (snapshot, False, None)

    old_status = appt.status
    appt.status = AppointmentStatus.CANCELLED

    db.add(
        AppointmentHistory(
            appointment_id=appt.id,
            tenant_id=tenant_id,
            event_type="cancelled",
            old_status=old_status.value,
            new_status=AppointmentStatus.CANCELLED.value,
            changed_by_user_id=changed_by_user_id,
            source=source,
            reason=reason,
        )
    )
    await db.commit()
    await db.refresh(appt)

    snapshot = await get_appointment_snapshot(db, appointment_id, tenant_id)
    if snapshot is None:
        raise AppointmentNotFoundError()
    return (snapshot, True, old_status.value)


async def reschedule_appointment(
    db: AsyncSession,
    appointment_id: int,
    tenant_id: int,
    *,
    new_start_time: datetime,
    new_end_time: datetime,
    changed_by_user_id: int | None = None,
    source: str = "api",
    reason: str | None = None,
) -> RescheduleResult:
    """
    Reschedule appointment to new start/end time.
    Idempotent if new times equal current times.

    Rules:
    - COMPLETED, NO_SHOW, CANCELLED → RescheduleForbiddenError
    - new_start_time >= new_end_time → RescheduleValidationError
    - Overlap with another appointment → RescheduleSlotConflictError
    - Same slot → idempotent, returns current snapshot with rescheduled=False

    Returns (snapshot, rescheduled). Raises AppointmentNotFoundError if not found.
    """
    stmt = (
        select(Appointment)
        .where(
            Appointment.id == appointment_id,
            Appointment.tenant_id == tenant_id,
            Appointment.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    appt = result.scalar_one_or_none()

    if not appt:
        raise AppointmentNotFoundError()

    if appt.status in RESCHEDULE_FORBIDDEN_STATUSES:
        raise RescheduleForbiddenError(
            f"Cannot reschedule appointment in status '{appt.status.value}'"
        )

    if new_start_time >= new_end_time:
        raise RescheduleValidationError(
            "new_start_time must be before new_end_time"
        )

    old_start = appt.start_time
    old_end = appt.end_time

    if old_start == new_start_time and old_end == new_end_time:
        snapshot = await get_appointment_snapshot(db, appointment_id, tenant_id)
        if snapshot is None:
            raise AppointmentNotFoundError()
        return (snapshot, False, old_start, old_end)

    conflict_stmt = (
        select(Appointment.id)
        .where(
            Appointment.shop_id == appt.shop_id,
            Appointment.id != appointment_id,
            Appointment.deleted_at.is_(None),
            Appointment.status.in_([
                AppointmentStatus.NEW.value,
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.IN_PROGRESS.value,
            ]),
            Appointment.start_time < new_end_time,
            Appointment.end_time > new_start_time,
        )
    )
    conflict_result = await db.execute(conflict_stmt)
    if conflict_result.scalars().first() is not None:
        raise RescheduleSlotConflictError("Target slot overlaps with another appointment")

    appt.start_time = new_start_time
    appt.end_time = new_end_time

    db.add(
        AppointmentHistory(
            appointment_id=appt.id,
            tenant_id=tenant_id,
            event_type="rescheduled",
            old_status=appt.status.value,
            new_status=appt.status.value,
            changed_by_user_id=changed_by_user_id,
            source=source,
            reason=reason,
            payload={
                "old_start_time": old_start.isoformat() if old_start else None,
                "old_end_time": old_end.isoformat() if old_end else None,
                "new_start_time": new_start_time.isoformat(),
                "new_end_time": new_end_time.isoformat(),
            },
        )
    )

    try:
        await db.commit()
        await db.refresh(appt)
    except IntegrityError:
        await db.rollback()
        raise RescheduleSlotConflictError("Target slot overlaps with another appointment")

    snapshot = await get_appointment_snapshot(db, appointment_id, tenant_id)
    if snapshot is None:
        raise AppointmentNotFoundError()
    return (snapshot, True, old_start, old_end)
