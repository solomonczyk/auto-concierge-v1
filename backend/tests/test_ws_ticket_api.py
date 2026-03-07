import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_issue_ws_ticket_authenticated_returns_200(client_auth: AsyncClient):
    """client_auth fixture already logs in and sets X-CSRF-Token."""
    response = await client_auth.post(f"{settings.API_V1_STR}/ws-ticket")
    assert response.status_code == 200

    data = response.json()
    assert "ticket" in data and isinstance(data["ticket"], str) and data["ticket"]
    assert data["expires_in"] == 45
    assert data["token_type"] == "ws_ticket"
