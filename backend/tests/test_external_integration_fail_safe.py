"""
Fail-safe tests for external_integration_service.
Critical audit risk: create/read flow must not break when integration fails.
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.api.endpoints import appointments as appointments_endpoint
from app.models.models import Appointment, Client, Service, Shop


@pytest.mark.asyncio
async def test_create_succeeds_despite_integration_runtime_error(
    client_auth: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Create appointment succeeds when enqueue_appointment raises RuntimeError."""

    def broken_enqueue(_appointment_id: int, _tenant_id: int) -> bool:
        raise RuntimeError("integration queue down")

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "enqueue_appointment",
        broken_enqueue,
    )

    appt_data = {
        "service_id": 1,
        "start_time": "2026-02-20T14:00:00",
        "client_name": "Fail-Safe Runtime",
        "client_phone": "+70000000101",
    }
    response = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
    )

    assert response.status_code == 200
    created = response.json()
    assert created["id"] > 0
    assert created["client_id"] > 0
    assert created["service_id"] == 1
    assert created["status"] == "new"


@pytest.mark.asyncio
async def test_create_record_persisted_in_db_despite_integration_failure(
    client_auth: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    """Appointment is actually saved to DB when integration fails."""
    def broken_enqueue(_appointment_id: int, _tenant_id: int) -> bool:
        raise ConnectionError("Redis unreachable")

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "enqueue_appointment",
        broken_enqueue,
    )

    appt_data = {
        "service_id": 1,
        "start_time": "2026-02-20T15:00:00",
        "client_name": "Fail-Safe Persisted",
        "client_phone": "+70000000102",
    }
    response = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
    )

    assert response.status_code == 200
    created = response.json()
    appt_id = created["id"]

    stmt = select(Appointment).where(Appointment.id == appt_id)
    result = await db_session.execute(stmt)
    appt = result.scalar_one_or_none()
    assert appt is not None
    assert appt.client_id == created["client_id"]
    assert appt.service_id == 1
    assert appt.tenant_id == 1


@pytest.mark.asyncio
async def test_create_no_500_on_name_error(
    client_auth: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """API must not return 500 when integration raises NameError (e.g. missing settings)."""
    def broken_enqueue(_appointment_id: int, _tenant_id: int) -> bool:
        raise NameError("settings.INTEGRATION_URL not defined")

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "enqueue_appointment",
        broken_enqueue,
    )

    appt_data = {
        "service_id": 1,
        "start_time": "2026-02-20T16:00:00",
        "client_name": "Fail-Safe NameError",
        "client_phone": "+70000000103",
    }
    response = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
    )

    assert response.status_code == 200
    assert response.json()["id"] > 0


@pytest.mark.asyncio
async def test_create_integration_error_logged(
    client_auth: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Integration failure is logged; main flow still succeeds."""
    def broken_enqueue(_appointment_id: int, _tenant_id: int) -> bool:
        raise RuntimeError("sync service unavailable")

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "enqueue_appointment",
        broken_enqueue,
    )

    with patch("app.api.endpoints.appointments.logger") as mock_logger:
        response = await client_auth.post(
            f"{settings.API_V1_STR}/appointments/",
            json={
                "service_id": 1,
                "start_time": "2026-02-20T17:00:00",
                "client_name": "Fail-Safe Logged",
                "client_phone": "+70000000104",
            },
        )

        assert response.status_code == 200
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0]
        assert "External integration enqueue failed" in call_args[0]
        assert "sync service unavailable" in str(call_args[2])
