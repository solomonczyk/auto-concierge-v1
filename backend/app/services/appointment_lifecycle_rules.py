"""
Appointment lifecycle rules (shared).

This module is deliberately dependency-light to avoid import cycles between:
- appointment_snapshot_service (read-model)
- appointment_lifecycle_service (write-model)

It centralizes status-based capability rules for cancel/reschedule.
"""

from app.models.models import AppointmentStatus


# Statuses that cannot be cancelled (self-service and operator flows)
CANCEL_FORBIDDEN_STATUSES = frozenset({
    AppointmentStatus.COMPLETED,
    AppointmentStatus.NO_SHOW,
})


# Statuses that cannot be rescheduled
RESCHEDULE_FORBIDDEN_STATUSES = frozenset({
    AppointmentStatus.COMPLETED,
    AppointmentStatus.NO_SHOW,
    AppointmentStatus.CANCELLED,
})


def can_cancel_appointment(*, status: AppointmentStatus) -> bool:
    """
    Whether a cancel action should be offered to the user.

    Note: lifecycle cancel is idempotent for CANCELLED, but UI capability should
    reflect whether the action is meaningful.
    """
    if status == AppointmentStatus.CANCELLED:
        return False
    return status not in CANCEL_FORBIDDEN_STATUSES


def can_reschedule_appointment(*, status: AppointmentStatus) -> bool:
    """Whether a reschedule action should be offered to the user."""
    return status not in RESCHEDULE_FORBIDDEN_STATUSES

