import pytest
from httpx import AsyncClient
from app.core.config import settings


@pytest.mark.asyncio
async def test_login_sets_cookie(client: AsyncClient):
    response = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    response = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "wrongpassword"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_me_returns_user_info(client: AsyncClient):
    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    response = await client.get(f"{settings.API_V1_STR}/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert "user_id" in data
    assert "tenant_id" in data
    assert "role" in data


@pytest.mark.asyncio
async def test_me_without_auth_returns_401(client: AsyncClient):
    response = await client.get(f"{settings.API_V1_STR}/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie(client: AsyncClient):
    await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert "access_token" in client.cookies

    response = await client.post(f"{settings.API_V1_STR}/auth/logout")
    assert response.status_code == 200

    me_response = await client.get(f"{settings.API_V1_STR}/me")
    assert me_response.status_code == 401
