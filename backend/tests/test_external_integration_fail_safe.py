"""
Fail-safe tests for external integration state on appointments.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.endpoints import appointments as appointments_endpoint
from app.core.config import settings
from app.services.appointment_integration_service import run_appointment_integration_sync
from app.services.outbox_service import (
    OUTBOX_ENTITY_APPOINTMENT,
    OUTBOX_EVENT_APPOINTMENT_CREATED,
)
from app.models.models import Appointment, AuditLog, IntegrationStatus, OutboxEvent


@pytest.mark.asyncio
async def test_create_appointment_marks_integration_failed_without_breaking_flow(
    client_auth: AsyncClient,
    db_session: AsyncSession,
):
    response = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": "2026-02-20T14:00:00",
            "client_name": "Fail-Safe Failed",
            "client_phone": "+70000000101",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["integration_status"] == "pending"

    result = await db_session.execute(select(Appointment).where(Appointment.id == payload["id"]))
    appointment = result.scalar_one()
    assert appointment.integration_status == IntegrationStatus.PENDING

    outbox_result = await db_session.execute(
        select(OutboxEvent)
        .where(
            OutboxEvent.entity_type == OUTBOX_ENTITY_APPOINTMENT,
            OutboxEvent.entity_id == str(payload["id"]),
            OutboxEvent.event_type == OUTBOX_EVENT_APPOINTMENT_CREATED,
        )
        .order_by(OutboxEvent.id.desc())
        .limit(1)
    )
    outbox_event = outbox_result.scalar_one_or_none()
    assert outbox_event is not None


@pytest.mark.asyncio
async def test_create_appointment_marks_integration_success(
    client_auth: AsyncClient,
    db_session: AsyncSession,
):
    response = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": "2026-02-20T15:00:00",
            "client_name": "Fail-Safe Success",
            "client_phone": "+70000000102",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["integration_status"] == "pending"

    result = await db_session.execute(select(Appointment).where(Appointment.id == payload["id"]))
    appointment = result.scalar_one()
    assert appointment.integration_status == IntegrationStatus.PENDING

    outbox_result = await db_session.execute(
        select(OutboxEvent)
        .where(
            OutboxEvent.entity_type == OUTBOX_ENTITY_APPOINTMENT,
            OutboxEvent.entity_id == str(payload["id"]),
            OutboxEvent.event_type == OUTBOX_EVENT_APPOINTMENT_CREATED,
        )
        .order_by(OutboxEvent.id.desc())
        .limit(1)
    )
    outbox_event = outbox_result.scalar_one_or_none()
    assert outbox_event is not None


@pytest.mark.asyncio
async def test_failed_integration_is_cleared_after_successful_retry(
    client_auth: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    async def failed_sync(_appointment_id: int, _tenant_id: int):
        return False, "crm timeout"

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "sync_appointment",
        failed_sync,
    )

    response = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": "2026-02-20T16:00:00",
            "client_name": "Fail-Safe Retry",
            "client_phone": "+70000000103",
        },
    )
    assert response.status_code == 200
    appointment_id = response.json()["id"]

    async def successful_sync(_appointment_id: int, _tenant_id: int):
        return True, None

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "sync_appointment",
        successful_sync,
    )

    appointment = await run_appointment_integration_sync(
        db=db_session,
        appointment_id=appointment_id,
        tenant_id=1,
    )

    assert appointment.integration_status == IntegrationStatus.SUCCESS
    assert appointment.last_integration_error is None
    assert appointment.last_integration_attempt_at is not None


@pytest.mark.asyncio
async def test_put_appointment_marks_integration_failed_without_breaking_flow(
    client_auth: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    create_response = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": "2026-02-20T17:00:00",
            "client_name": "PUT Fail-Safe",
            "client_phone": "+70000000104",
        },
    )
    assert create_response.status_code == 200
    appointment_id = create_response.json()["id"]

    async def failed_sync(_appointment_id: int, _tenant_id: int):
        return False, "crm put timeout"

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "sync_appointment",
        failed_sync,
    )

    put_response = await client_auth.put(
        f"{settings.API_V1_STR}/appointments/{appointment_id}",
        json={"car_make": "Toyota"},
    )

    assert put_response.status_code == 200
    payload = put_response.json()
    assert payload["auto_info"] is not None
    assert payload["auto_info"]["car_make"] == "Toyota"
    assert payload["integration_status"] == "failed"
    assert payload["last_integration_error"] == "crm put timeout"
    assert payload["last_integration_attempt_at"] is not None

    result = await db_session.execute(
        select(Appointment)
        .options(selectinload(Appointment.auto_snapshot))
        .where(Appointment.id == appointment_id)
    )
    appointment = result.scalar_one()
    assert appointment.auto_snapshot is not None
    assert appointment.auto_snapshot.car_make == "Toyota"
    assert appointment.integration_status == IntegrationStatus.FAILED

    audit_result = await db_session.execute(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "appointment",
            AuditLog.entity_id == str(appointment_id),
            AuditLog.action == "integration_failed",
        )
        .order_by(AuditLog.id.desc())
    )
    audit_entry = audit_result.scalars().first()
    assert audit_entry is not None
    assert audit_entry.payload_after["integration_status"] == "failed"
    assert audit_entry.payload_after["last_integration_error"] == "crm put timeout"


@pytest.mark.asyncio
async def test_patch_status_marks_integration_failed_without_breaking_flow(
    client_auth: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    create_response = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": "2026-02-20T18:00:00",
            "client_name": "PATCH Fail-Safe",
            "client_phone": "+70000000105",
        },
    )
    assert create_response.status_code == 200
    appointment_id = create_response.json()["id"]

    async def failed_sync(_appointment_id: int, _tenant_id: int):
        return False, "crm status timeout"

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "sync_appointment",
        failed_sync,
    )

    patch_response = await client_auth.patch(
        f"{settings.API_V1_STR}/appointments/{appointment_id}/status",
        json={"status": "confirmed"},
    )

    assert patch_response.status_code == 200
    payload = patch_response.json()
    assert payload["status"] == "confirmed"
    assert payload["integration_status"] == "failed"
    assert payload["last_integration_error"] == "crm status timeout"
    assert payload["last_integration_attempt_at"] is not None

    result = await db_session.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one()
    assert appointment.status.value == "confirmed"
    assert appointment.integration_status == IntegrationStatus.FAILED


@pytest.mark.asyncio
async def test_put_appointment_clears_previous_integration_error_after_success(
    client_auth: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    create_response = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": "2026-02-20T19:00:00",
            "client_name": "Recovery PUT",
            "client_phone": "+70000000106",
        },
    )
    assert create_response.status_code == 200
    appointment_id = create_response.json()["id"]
    assert create_response.json()["integration_status"] == "pending"

    async def successful_sync(_appointment_id: int, _tenant_id: int):
        return True, None

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "sync_appointment",
        successful_sync,
    )

    put_response = await client_auth.put(
        f"{settings.API_V1_STR}/appointments/{appointment_id}",
        json={"car_year": 2021},
    )

    assert put_response.status_code == 200
    payload = put_response.json()
    assert payload["auto_info"] is not None
    assert payload["auto_info"]["car_year"] == 2021
    assert payload["integration_status"] == "success"
    assert payload["last_integration_error"] is None
    assert payload["last_integration_attempt_at"] is not None

    result = await db_session.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one()
    assert appointment.integration_status == IntegrationStatus.SUCCESS
    assert appointment.last_integration_error is None
