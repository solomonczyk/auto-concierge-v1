"""
Tests for services API endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_service(client: AsyncClient, auth_headers: dict):
    """Test creating a new service."""
    service_data = {
        "name": "Test Service",
        "description": "Test description",
        "base_price": 1000.0,
        "duration_minutes": 60
    }
    
    response = await client.post(
        "/api/v1/services/",
        json=service_data,
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == service_data["name"]
    assert data["base_price"] == service_data["base_price"]


@pytest.mark.asyncio
async def test_get_services(client: AsyncClient, auth_headers: dict):
    """Test getting list of services."""
    response = await client.get("/api/v1/services/", headers=auth_headers)
    
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_service_unauthorized(client: AsyncClient):
    """Test creating service without authentication."""
    service_data = {
        "name": "Test Service",
        "description": "Test description",
        "base_price": 1000.0,
        "duration_minutes": 60
    }
    
    response = await client.post("/api/v1/services/", json=service_data)
    
    # Should fail without auth
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_service_validation(client: AsyncClient, auth_headers: dict):
    """Test service validation - empty name."""
    service_data = {
        "name": "",
        "base_price": 1000.0,
        "duration_minutes": 60
    }
    
    response = await client.post(
        "/api/v1/services/",
        json=service_data,
        headers=auth_headers
    )
    
    # Should fail validation
    assert response.status_code == 422
