"""
Appointment lifecycle actions service.

Cancel is the canonical lifecycle action. All future flows (Telegram WebApp,
operator dashboard, reminders, self-service) must use this service or its HTTP
endpoint — do not scatter cancel logic elsewhere.

Contract: see docs/APPOINTMENT_LIFECYCLE.md
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
