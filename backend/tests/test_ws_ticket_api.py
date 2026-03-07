import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_issue_ws_ticket_authenticated_returns_200(client: AsyncClient):
    login_response = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200

    response = await client.post(f"{settings.API_V1_STR}/ws-ticket")
    assert response.status_code == 200

    data = response.json()
    assert "ticket" in data and isinstance(data["ticket"], str) and data["ticket"]
    assert data["expires_in"] == 45
    assert data["token_type"] == "ws_ticket"
