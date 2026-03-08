"""
Appointment external integration sync. Updates appointment integration_status
based on external_integration.sync_appointment result.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.metrics import APPOINTMENTS_EXTERNAL_SYNC_FAILED_TOTAL
from app.models.models import Appointment, IntegrationStatus
from app.services.audit_service import log_audit
from app.services.external_integration_service import external_integration

logger = logging.getLogger(__name__)

INTEGRATION_ERROR_MAX_LENGTH = 500


def _short_integration_error(error: object | None) -> str | None:
    if error is None:
        return None
    message = str(error).strip()
    if not message:
        message = "External integration sync failed"
    return message[:INTEGRATION_ERROR_MAX_LENGTH]


async def _set_appointment_integration_state(
    *,
    db: AsyncSession,
    appointment_id: int,
    tenant_id: int,
    status_value: IntegrationStatus,
    error_message: str | None = None,
) -> Appointment | None:
    stmt = select(Appointment).options(
        joinedload(Appointment.client),
        joinedload(Appointment.service),
        selectinload(Appointment.auto_snapshot),
    ).where(and_(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id))
    result = await db.execute(stmt)
    appointment = result.scalar_one_or_none()
    if appointment is None:
        appointment = await db.get(
            Appointment,
            appointment_id,
            options=(joinedload(Appointment.client), joinedload(Appointment.service), selectinload(Appointment.auto_snapshot)),
        )
        if appointment and appointment.tenant_id != tenant_id:
            appointment = None

    if appointment is None:
        logger.warning(
            "Skipping integration state update: appointment not found appointment_id=%s tenant_id=%s status=%s",
            appointment_id,
            tenant_id,
            status_value.value,
        )
        return None

    previous_status = appointment.integration_status
    previous_error = appointment.last_integration_error

    appointment.integration_status = status_value
    appointment.last_integration_error = None if status_value == IntegrationStatus.SUCCESS else error_message
    appointment.last_integration_attempt_at = datetime.now(timezone.utc)

    if status_value == IntegrationStatus.FAILED:
        await log_audit(
            db,
            tenant_id=appointment.tenant_id,
            actor_user_id=None,
            action="integration_failed",
            entity_type="appointment",
            entity_id=str(appointment.id),
            payload_after={
                "integration_status": status_value.value,
                "last_integration_error": appointment.last_integration_error,
            },
            source="system",
        )
    elif previous_status == IntegrationStatus.FAILED and previous_error:
        await log_audit(
            db,
            tenant_id=appointment.tenant_id,
            actor_user_id=None,
            action="integration_recovered",
            entity_type="appointment",
            entity_id=str(appointment.id),
            payload_before={
                "integration_status": previous_status.value,
                "last_integration_error": previous_error,
            },
            payload_after={
                "integration_status": status_value.value,
                "last_integration_error": None,
            },
            source="system",
        )

    await db.commit()
    refreshed_stmt = select(Appointment).options(
        joinedload(Appointment.client),
        joinedload(Appointment.service),
    ).where(and_(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id))
    refreshed_result = await db.execute(refreshed_stmt)
    refreshed_appointment = refreshed_result.scalar_one_or_none()
    if refreshed_appointment is None:
        logger.warning(
            "Integration state updated but refreshed appointment not found appointment_id=%s tenant_id=%s",
            appointment_id,
            tenant_id,
        )
        return appointment
    return refreshed_appointment


async def run_appointment_integration_sync(
    *,
    db: AsyncSession,
    appointment_id: int,
    tenant_id: int,
) -> Appointment:
    try:
        integration_result = await external_integration.sync_appointment(appointment_id, tenant_id)
        if isinstance(integration_result, tuple):
            sync_ok, sync_error = integration_result
        else:
            sync_ok = bool(integration_result)
            sync_error = None if sync_ok else "External integration sync failed"
    except Exception as integration_error:
        sync_ok = False
        sync_error = integration_error

    error_message = _short_integration_error(sync_error)

    if sync_ok:
        return await _set_appointment_integration_state(
            db=db,
            appointment_id=appointment_id,
            tenant_id=tenant_id,
            status_value=IntegrationStatus.SUCCESS,
        )

    APPOINTMENTS_EXTERNAL_SYNC_FAILED_TOTAL.labels(
        tenant_id=str(tenant_id)
    ).inc()
    logger.error(
        "External integration sync failed for appointment %s: %s",
        appointment_id,
        error_message,
    )
    return await _set_appointment_integration_state(
        db=db,
        appointment_id=appointment_id,
        tenant_id=tenant_id,
        status_value=IntegrationStatus.FAILED,
        error_message=error_message,
    )
