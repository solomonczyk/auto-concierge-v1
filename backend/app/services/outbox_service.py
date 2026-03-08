from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import OutboxEvent

MAX_OUTBOX_ATTEMPTS = 10
OUTBOX_RETRY_DELAY_SECONDS = 60
OUTBOX_EVENT_APPOINTMENT_CREATED = "appointment_created"
OUTBOX_ENTITY_APPOINTMENT = "appointment"
OUTBOX_PAYLOAD_APPOINTMENT_ID = "appointment_id"
OUTBOX_PAYLOAD_TENANT_ID = "tenant_id"


async def enqueue_outbox_event(
    db: AsyncSession,
    *,
    tenant_id: int,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict,
) -> None:
    event = OutboxEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )

    db.add(event)


async def enqueue_appointment_created_event(
    db: AsyncSession,
    *,
    tenant_id: int,
    appointment_id: int,
) -> None:
    await enqueue_outbox_event(
        db,
        tenant_id=tenant_id,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id=str(appointment_id),
        payload={
            OUTBOX_PAYLOAD_APPOINTMENT_ID: appointment_id,
            OUTBOX_PAYLOAD_TENANT_ID: tenant_id,
        },
    )


async def fetch_pending_outbox_events(
    db: AsyncSession,
    *,
    limit: int = 100,
) -> list[OutboxEvent]:
    stmt = (
        select(OutboxEvent)
        .where(
            OutboxEvent.status == "pending",
            OutboxEvent.available_at <= datetime.now(timezone.utc),
        )
        .order_by(OutboxEvent.available_at.asc(), OutboxEvent.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def mark_outbox_events_processing(
    events: list[OutboxEvent],
) -> None:
    for event in events:
        event.status = "processing"
        event.attempts = (event.attempts or 0) + 1


async def mark_outbox_event_processed(
    event: OutboxEvent,
) -> None:
    event.status = "processed"
    event.last_error = None


async def mark_outbox_event_failed(
    event: OutboxEvent,
    error_message: str,
    retry_delay_seconds: int = OUTBOX_RETRY_DELAY_SECONDS,
) -> None:
    if (event.attempts or 0) >= MAX_OUTBOX_ATTEMPTS:
        event.status = "failed"
        event.last_error = error_message
        return

    event.status = "pending"
    event.last_error = error_message
    event.available_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay_seconds)


async def dispatch_outbox_event(
    event: OutboxEvent,
    db: AsyncSession,
) -> None:
    try:
        from app.services.outbox_dispatcher import handle_outbox_event

        await handle_outbox_event(event, db)
        await mark_outbox_event_processed(event)
    except Exception as e:
        await mark_outbox_event_failed(event, str(e))


async def process_outbox_batch(
    db: AsyncSession,
    limit: int = 100,
) -> None:
    events = await fetch_pending_outbox_events(db, limit=limit)
    await mark_outbox_events_processing(events)
    await db.flush()

    for event in events:
        await dispatch_outbox_event(event, db)
        await db.flush()


async def run_outbox_once(
    db: AsyncSession,
    limit: int = 100,
) -> None:
    await process_outbox_batch(db, limit=limit)
    await db.commit()
