import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.models.models import UserRole


@pytest.mark.asyncio
async def test_read_services(client_auth: AsyncClient):
    response = await client_auth.get(f"{settings.API_V1_STR}/services/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_service_admin(client_auth: AsyncClient):
    service_data = {
        "name": "Test Service",
        "duration_minutes": 45,
        "base_price": 1500.0,
    }
    response = await client_auth.post(
        f"{settings.API_V1_STR}/services/",
        json=service_data,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Service"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_create_service_unauthorized(client: AsyncClient):
    service_data = {
        "name": "Unauthorized Service",
        "duration_minutes": 30,
        "base_price": 500.0,
    }
    response = await client.post(
        f"{settings.API_V1_STR}/services/",
        json=service_data,
    )
    assert response.status_code == 401
