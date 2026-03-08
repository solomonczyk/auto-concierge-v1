import pytest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from sqlalchemy import text

from app.models.models import OutboxEvent
from app.services.outbox_service import (
    MAX_OUTBOX_ATTEMPTS,
    OUTBOX_ENTITY_APPOINTMENT,
    OUTBOX_EVENT_APPOINTMENT_CREATED,
    OUTBOX_PAYLOAD_APPOINTMENT_ID,
    OUTBOX_PAYLOAD_TENANT_ID,
    OUTBOX_RETRY_DELAY_SECONDS,
    dispatch_outbox_event,
    mark_outbox_event_failed,
    mark_outbox_event_processed,
    mark_outbox_events_processing,
    process_outbox_batch,
    run_outbox_once,
)


@pytest.mark.asyncio
async def test_run_outbox_once_smoke(db_session):
    await run_outbox_once(db_session)


@pytest.mark.asyncio
async def test_mark_outbox_event_failed_sets_retry_state():
    event = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="1",
        payload={},
        status="processing",
        attempts=1,
        available_at=datetime.now(timezone.utc),
    )

    before = datetime.now(timezone.utc)
    await mark_outbox_event_failed(event, "boom", retry_delay_seconds=60)

    assert event.status == "pending"
    assert event.last_error == "boom"
    assert event.available_at > before


@pytest.mark.asyncio
async def test_mark_outbox_event_failed_marks_failed_after_max_attempts():
    current_available_at = datetime.now(timezone.utc)

    event = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="max-attempts",
        payload={},
        status="processing",
        attempts=MAX_OUTBOX_ATTEMPTS,
        available_at=current_available_at,
    )

    await mark_outbox_event_failed(event, "boom", retry_delay_seconds=60)

    assert event.status == "failed"
    assert event.last_error == "boom"
    assert event.available_at == current_available_at


@pytest.mark.asyncio
async def test_mark_outbox_event_processed_clears_error():
    event = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="1",
        payload={},
        status="processing",
        attempts=1,
        last_error="boom",
    )

    await mark_outbox_event_processed(event)

    assert event.status == "processed"
    assert event.last_error is None


@pytest.mark.asyncio
async def test_mark_outbox_events_processing_sets_status_and_increments_attempts():
    event1 = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="1",
        payload={},
        status="pending",
        attempts=0,
    )
    event2 = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="2",
        payload={},
        status="pending",
        attempts=None,
    )

    await mark_outbox_events_processing([event1, event2])

    assert event1.status == "processing"
    assert event1.attempts == 1

    assert event2.status == "processing"
    assert event2.attempts == 1


@pytest.mark.asyncio
async def test_dispatch_outbox_event_success(db_session, monkeypatch):
    called = {"value": False}

    async def fake_handle(event, db):
        called["value"] = True

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.handle_outbox_event",
        fake_handle,
    )

    event = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="1",
        payload={},
        status="processing",
        attempts=1,
        last_error="old error",
    )

    await dispatch_outbox_event(event, db_session)

    assert called["value"] is True
    assert event.status == "processed"
    assert event.last_error is None


@pytest.mark.asyncio
async def test_dispatch_outbox_event_failure_sets_retry_state(db_session, monkeypatch):
    async def fake_handle(event, db):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.handle_outbox_event",
        fake_handle,
    )

    event = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="1",
        payload={},
        status="processing",
        attempts=1,
        available_at=datetime.now(timezone.utc),
    )

    before = datetime.now(timezone.utc)
    await dispatch_outbox_event(event, db_session)

    assert event.status == "pending"
    assert event.last_error == "boom"
    assert event.available_at > before


@pytest.mark.asyncio
async def test_process_outbox_batch_processes_pending_events(db_session, monkeypatch):
    processed_ids = []

    async def fake_handle(event, db):
        processed_ids.append(event.entity_id)

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.handle_outbox_event",
        fake_handle,
    )

    event1 = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="1",
        payload={},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    event2 = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="2",
        payload={},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )

    db_session.add_all([event1, event2])
    await db_session.flush()

    await process_outbox_batch(db_session, limit=100)

    assert processed_ids == ["1", "2"]
    assert event1.status == "processed"
    assert event2.status == "processed"
    assert event1.last_error is None
    assert event2.last_error is None


@pytest.mark.asyncio
async def test_run_outbox_once_commits_processed_state(db_session, monkeypatch):
    async def fake_handle(event, db):
        return None

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.handle_outbox_event",
        fake_handle,
    )

    event = OutboxEvent(
        tenant_id=1,
        event_type="test",
        entity_type="test",
        entity_id="commit-check",
        payload={},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()

    await run_outbox_once(db_session, limit=100)

    refreshed = await db_session.get(OutboxEvent, event.id)
    assert refreshed is not None
    assert refreshed.status == "processed"
    assert refreshed.last_error is None


# --- handle_outbox_event fail-closed tests ---


@pytest.mark.asyncio
async def test_handle_outbox_event_unknown_event_type_raises(db_session):
    from app.services.outbox_dispatcher import handle_outbox_event

    event = SimpleNamespace(
        event_type="unknown_type",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 1, OUTBOX_PAYLOAD_TENANT_ID: 1},
    )
    with pytest.raises(ValueError, match=r"Unsupported outbox event_type: unknown_type"):
        await handle_outbox_event(event, db_session)


@pytest.mark.asyncio
async def test_handle_outbox_event_payload_not_dict_raises(db_session):
    from app.services.outbox_dispatcher import handle_outbox_event

    event = SimpleNamespace(event_type=OUTBOX_EVENT_APPOINTMENT_CREATED, payload=None)
    with pytest.raises(ValueError, match=r"payload must be a non-empty dict"):
        await handle_outbox_event(event, db_session)


@pytest.mark.asyncio
async def test_handle_outbox_event_payload_empty_dict_raises(db_session):
    from app.services.outbox_dispatcher import handle_outbox_event

    event = SimpleNamespace(event_type=OUTBOX_EVENT_APPOINTMENT_CREATED, payload={})
    with pytest.raises(ValueError, match=r"payload must be a non-empty dict"):
        await handle_outbox_event(event, db_session)


@pytest.mark.asyncio
async def test_handle_outbox_event_payload_missing_ids_raises(db_session):
    from app.services.outbox_dispatcher import handle_outbox_event

    event = SimpleNamespace(
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 1},
    )
    with pytest.raises(ValueError, match=r"missing appointment_id or tenant_id"):
        await handle_outbox_event(event, db_session)

    event2 = SimpleNamespace(
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        payload={OUTBOX_PAYLOAD_TENANT_ID: 1},
    )
    with pytest.raises(ValueError, match=r"missing appointment_id or tenant_id"):
        await handle_outbox_event(event2, db_session)


@pytest.mark.asyncio
async def test_handle_outbox_event_invalid_int_ids_raises(db_session):
    from app.services.outbox_dispatcher import handle_outbox_event

    event = SimpleNamespace(
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: "abc", OUTBOX_PAYLOAD_TENANT_ID: 1},
    )
    with pytest.raises(ValueError, match=r"must be valid integers"):
        await handle_outbox_event(event, db_session)


@pytest.mark.asyncio
async def test_handle_outbox_event_valid_payload_calls_sync(db_session, monkeypatch):
    from app.services.outbox_dispatcher import handle_outbox_event

    called = []

    async def fake_sync(*, db, appointment_id, tenant_id):
        called.append({OUTBOX_PAYLOAD_APPOINTMENT_ID: appointment_id, OUTBOX_PAYLOAD_TENANT_ID: tenant_id})

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.run_appointment_integration_sync",
        fake_sync,
    )

    event = SimpleNamespace(
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 42, OUTBOX_PAYLOAD_TENANT_ID: 7},
    )
    await handle_outbox_event(event, db_session)

    assert len(called) == 1
    assert called[0][OUTBOX_PAYLOAD_APPOINTMENT_ID] == 42
    assert called[0][OUTBOX_PAYLOAD_TENANT_ID] == 7
    assert isinstance(called[0][OUTBOX_PAYLOAD_APPOINTMENT_ID], int)
    assert isinstance(called[0][OUTBOX_PAYLOAD_TENANT_ID], int)


@pytest.mark.asyncio
async def test_run_outbox_once_invalid_payload_marks_failed_not_processed(db_session):
    """Invalid payload: event must not be marked processed; must get retry state with error."""
    event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="invalid-payload-test",
        payload={},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    await run_outbox_once(db_session, limit=100)

    refreshed = await db_session.get(OutboxEvent, event_id)
    assert refreshed is not None
    assert refreshed.status != "processed"
    assert refreshed.attempts == 1
    assert refreshed.last_error is not None
    assert "payload" in refreshed.last_error.lower() or "dict" in refreshed.last_error.lower()


@pytest.mark.asyncio
async def test_run_outbox_once_valid_payload_marks_processed(db_session, monkeypatch):
    async def fake_sync(*, db, appointment_id, tenant_id):
        return None

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.run_appointment_integration_sync",
        fake_sync,
    )

    event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="valid-payload-test",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 42, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    await run_outbox_once(db_session, limit=100)

    refreshed = await db_session.get(OutboxEvent, event_id)
    assert refreshed is not None
    assert refreshed.status == "processed"
    assert refreshed.attempts == 1
    assert refreshed.last_error is None


@pytest.mark.asyncio
async def test_run_outbox_once_unknown_event_type_keeps_event_unprocessed(db_session):
    event = OutboxEvent(
        tenant_id=1,
        event_type="unknown_type",
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="unknown-event-type-test",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 42, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    await run_outbox_once(db_session, limit=100)

    refreshed = await db_session.get(OutboxEvent, event_id)
    assert refreshed is not None
    assert refreshed.status != "processed"
    assert refreshed.attempts == 1
    assert refreshed.last_error is not None
    assert "unsupported outbox event_type" in refreshed.last_error.lower()


@pytest.mark.asyncio
async def test_run_outbox_once_limit_respects_batch_size(db_session, monkeypatch):
    called = []

    async def fake_sync(*, db, appointment_id, tenant_id):
        called.append(1)

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.run_appointment_integration_sync",
        fake_sync,
    )

    event1 = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="limit-test-1",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 1, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    event2 = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="limit-test-2",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 2, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    db_session.add_all([event1, event2])
    await db_session.flush()
    id1, id2 = event1.id, event2.id

    await run_outbox_once(db_session, limit=1)

    first = await db_session.get(OutboxEvent, id1)
    second = await db_session.get(OutboxEvent, id2)
    assert first is not None
    assert second is not None
    assert first.status == "processed"
    assert second.status == "pending"
    assert second.attempts == 0
    assert len(called) == 1


@pytest.mark.asyncio
async def test_run_outbox_once_processes_earliest_available_first(db_session, monkeypatch):
    called = []

    async def fake_sync(*, db, appointment_id, tenant_id):
        called.append(appointment_id)

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.run_appointment_integration_sync",
        fake_sync,
    )

    now = datetime.now(timezone.utc)
    early_event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="order-test-early",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 2, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=now - timedelta(seconds=5),
    )
    late_event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="order-test-late",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 1, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=now,
    )
    db_session.add_all([early_event, late_event])
    await db_session.flush()
    early_id, late_id = early_event.id, late_event.id

    await run_outbox_once(db_session, limit=1)

    early = await db_session.get(OutboxEvent, early_id)
    late = await db_session.get(OutboxEvent, late_id)
    assert early is not None
    assert late is not None
    assert early.status == "processed"
    assert late.status == "pending"
    assert called == [2]


@pytest.mark.asyncio
async def test_run_outbox_once_same_available_at_uses_id_tiebreak(db_session, monkeypatch):
    called = []

    async def fake_sync(*, db, appointment_id, tenant_id):
        called.append(appointment_id)

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.run_appointment_integration_sync",
        fake_sync,
    )

    await db_session.execute(text("DELETE FROM outbox_events"))
    await db_session.flush()

    now = datetime.now(timezone.utc)

    first_event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="tie-break-1",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 101, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=now,
    )
    second_event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="tie-break-2",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 202, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=now,
    )

    db_session.add_all([first_event, second_event])
    await db_session.flush()

    first_id, second_id = first_event.id, second_event.id
    assert first_id < second_id

    await run_outbox_once(db_session, limit=1)

    first = await db_session.get(OutboxEvent, first_id)
    second = await db_session.get(OutboxEvent, second_id)

    assert first.status == "processed"
    assert second.status == "pending"
    assert second.attempts == 0
    assert called == [101]


@pytest.mark.asyncio
async def test_run_outbox_once_skips_future_available_event(db_session, monkeypatch):
    called = []

    async def fake_sync(*, db, appointment_id, tenant_id):
        called.append(appointment_id)

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.run_appointment_integration_sync",
        fake_sync,
    )

    await db_session.execute(text("DELETE FROM outbox_events"))
    await db_session.flush()

    future_event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="future-event-test",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 555, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(future_event)
    await db_session.flush()
    event_id = future_event.id

    await run_outbox_once(db_session, limit=100)

    refreshed = await db_session.get(OutboxEvent, event_id)
    assert refreshed is not None
    assert refreshed.status == "pending"
    assert refreshed.attempts == 0
    assert refreshed.last_error is None
    assert called == []


@pytest.mark.asyncio
async def test_run_outbox_once_processes_only_pending_ignores_processed_failed(db_session, monkeypatch):
    called = []

    async def fake_sync(*, db, appointment_id, tenant_id):
        called.append(appointment_id)

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.run_appointment_integration_sync",
        fake_sync,
    )

    await db_session.execute(text("DELETE FROM outbox_events"))
    await db_session.flush()

    now = datetime.now(timezone.utc)

    pending_event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="pending-only",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 1, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=now,
    )
    already_processed_event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="already-processed",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 2, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="processed",
        attempts=1,
        available_at=now,
    )
    already_failed_event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="already-failed",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 3, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="failed",
        attempts=MAX_OUTBOX_ATTEMPTS,
        last_error="gave up",
        available_at=now,
    )
    db_session.add_all([pending_event, already_processed_event, already_failed_event])
    await db_session.flush()
    pending_id = pending_event.id
    processed_id = already_processed_event.id
    failed_id = already_failed_event.id

    await run_outbox_once(db_session, limit=10)

    pending = await db_session.get(OutboxEvent, pending_id)
    already_processed = await db_session.get(OutboxEvent, processed_id)
    already_failed = await db_session.get(OutboxEvent, failed_id)

    assert pending.status == "processed"
    assert already_processed.status == "processed"
    assert already_failed.status == "failed"
    assert len(called) == 1


@pytest.mark.asyncio
async def test_run_outbox_once_failure_pushes_available_at_forward(db_session):
    original_available_at = datetime.now(timezone.utc)

    event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="retry-backoff-test",
        payload={},
        status="pending",
        attempts=0,
        available_at=original_available_at,
    )
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    await run_outbox_once(db_session, limit=100)

    refreshed = await db_session.get(OutboxEvent, event_id)
    assert refreshed is not None
    assert refreshed.status != "processed"
    assert refreshed.attempts == 1
    assert refreshed.last_error is not None
    assert refreshed.available_at >= original_available_at + timedelta(seconds=OUTBOX_RETRY_DELAY_SECONDS)


@pytest.mark.asyncio
async def test_run_outbox_once_max_attempts_transitions_to_failed(db_session):
    original_available_at = datetime.now(timezone.utc)

    event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="max-attempts-terminal-test",
        payload={},
        status="pending",
        attempts=MAX_OUTBOX_ATTEMPTS - 1,
        available_at=original_available_at,
    )
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    await run_outbox_once(db_session, limit=100)

    refreshed = await db_session.get(OutboxEvent, event_id)
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert refreshed.attempts == MAX_OUTBOX_ATTEMPTS
    assert refreshed.last_error is not None


@pytest.mark.asyncio
async def test_run_outbox_once_valid_event_marks_processed_and_commits(db_session, monkeypatch):
    async def fake_handle(event, db):
        return None

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.handle_outbox_event",
        fake_handle,
    )

    event = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="success-path-test",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 123, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    await run_outbox_once(db_session, limit=100)

    refreshed = await db_session.get(OutboxEvent, event_id)
    assert refreshed is not None
    assert refreshed.status == "processed"
    assert refreshed.attempts == 1
    assert refreshed.last_error is None


@pytest.mark.asyncio
async def test_run_outbox_once_unknown_event_marks_failed(db_session):
    event = OutboxEvent(
        tenant_id=1,
        event_type="unknown_event_type",
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="unknown-event-test",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 123, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()
    event_id = event.id

    await run_outbox_once(db_session, limit=100)

    refreshed = await db_session.get(OutboxEvent, event_id)
    assert refreshed is not None
    assert refreshed.status != "processed"
    assert refreshed.attempts == 1
    assert refreshed.last_error is not None
    assert "unknown" in refreshed.last_error.lower() or "unsupported" in refreshed.last_error.lower()


@pytest.mark.asyncio
async def test_run_outbox_once_respects_limit(db_session, monkeypatch):
    async def fake_handle(event, db):
        return None

    monkeypatch.setattr(
        "app.services.outbox_dispatcher.handle_outbox_event",
        fake_handle,
    )

    event1 = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="limit-test-1",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 101, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )
    event2 = OutboxEvent(
        tenant_id=1,
        event_type=OUTBOX_EVENT_APPOINTMENT_CREATED,
        entity_type=OUTBOX_ENTITY_APPOINTMENT,
        entity_id="limit-test-2",
        payload={OUTBOX_PAYLOAD_APPOINTMENT_ID: 102, OUTBOX_PAYLOAD_TENANT_ID: 1},
        status="pending",
        attempts=0,
        available_at=datetime.now(timezone.utc),
    )

    db_session.add_all([event1, event2])
    await db_session.flush()

    event1_id = event1.id
    event2_id = event2.id

    await run_outbox_once(db_session, limit=1)

    refreshed1 = await db_session.get(OutboxEvent, event1_id)
    refreshed2 = await db_session.get(OutboxEvent, event2_id)

    assert refreshed1 is not None
    assert refreshed1.status == "processed"
    assert refreshed1.attempts == 1

    assert refreshed2 is not None
    assert refreshed2.status == "pending"
    assert refreshed2.attempts == 0
