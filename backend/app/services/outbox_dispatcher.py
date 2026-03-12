"""
Event handlers for transactional outbox. Called by dispatch_outbox_event.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.appointment_integration_service import run_appointment_integration_sync
from app.services.outbox_service import (
    OUTBOX_EVENT_APPOINTMENT_CREATED,
    OUTBOX_EVENT_APPOINTMENT_UPDATED,
    OUTBOX_PAYLOAD_APPOINTMENT_ID,
    OUTBOX_PAYLOAD_TENANT_ID,
)

_SUPPORTED_APPOINTMENT_EVENTS = (OUTBOX_EVENT_APPOINTMENT_CREATED, OUTBOX_EVENT_APPOINTMENT_UPDATED)


async def handle_outbox_event(event, db: AsyncSession) -> None:
    """Dispatch event to side effects. Fail-closed: no silent no-ops."""
    if event.event_type not in _SUPPORTED_APPOINTMENT_EVENTS:
        raise ValueError(f"Unsupported outbox event_type: {event.event_type}")

    payload = event.payload
    if not isinstance(payload, dict) or not payload:
        raise ValueError("Outbox event payload must be a non-empty dict")

    appointment_id = payload.get(OUTBOX_PAYLOAD_APPOINTMENT_ID)
    tenant_id = payload.get(OUTBOX_PAYLOAD_TENANT_ID)
    if appointment_id is None or tenant_id is None:
        raise ValueError("Outbox event payload missing appointment_id or tenant_id")

    try:
        appointment_id = int(appointment_id)
        tenant_id = int(tenant_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("appointment_id and tenant_id must be valid integers") from exc

    await run_appointment_integration_sync(
        db=db,
        appointment_id=appointment_id,
        tenant_id=tenant_id,
    )
