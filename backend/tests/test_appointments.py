import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.api.endpoints import appointments as appointments_endpoint


@pytest.mark.asyncio
async def test_create_appointment_unauthorized(client: AsyncClient):
    appt_data = {
        "shop_id": 1,
        "service_id": 1,
        "start_time": "2026-02-20T10:00:00",
        "client_name": "Test User",
        "client_phone": "+1234567890",
    }
    response = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_appointment_authorized(client: AsyncClient):
    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    appt_data = {
        "service_id": 1,
        "start_time": "2026-02-20T12:00:00",
        "client_name": "Authorized User",
        "client_phone": "+0987654321",
    }
    response = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["client_id"]
    assert data["shop_id"] == 1


@pytest.mark.asyncio
async def test_create_appointment_survives_external_integration_failure(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Regression: integration failure must not break appointment creation API."""
    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    def broken_enqueue(_appointment_id: int, _tenant_id: int) -> bool:
        raise RuntimeError("integration queue down")

    monkeypatch.setattr(
        appointments_endpoint.external_integration,
        "enqueue_appointment",
        broken_enqueue,
    )

    appt_data = {
        "service_id": 1,
        "start_time": "2026-02-20T13:00:00",
        "client_name": "Integration Failure Safe",
        "client_phone": "+70000000001",
    }
    create_res = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json=appt_data,
    )

    assert create_res.status_code == 200
    created = create_res.json()
    assert created["id"] > 0
    assert created["client_id"] > 0
    assert created["service_id"] == 1

    list_res = await client.get(f"{settings.API_V1_STR}/appointments/")
    assert list_res.status_code == 200
    ids = {item["id"] for item in list_res.json()}
    assert created["id"] in ids
