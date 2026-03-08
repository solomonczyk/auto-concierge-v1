import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import Tenant, TenantStatus


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
async def test_me_returns_user_info(client_auth: AsyncClient):
    response = await client_auth.get(f"{settings.API_V1_STR}/me")
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
async def test_logout_clears_cookie(client_auth: AsyncClient):
    assert "access_token" in client_auth.cookies

    response = await client_auth.post(f"{settings.API_V1_STR}/auth/logout")
    assert response.status_code == 200

    me_response = await client_auth.get(f"{settings.API_V1_STR}/me")
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_login_suspended_tenant_returns_403(client: AsyncClient, db_session: AsyncSession):
    """Suspended tenant blocks login with 403."""
    r = await db_session.execute(select(Tenant).where(Tenant.id == 1))
    tenant = r.scalar_one()
    tenant.status = TenantStatus.SUSPENDED
    await db_session.commit()

    response = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 403
    assert "suspended" in response.json().get("detail", "").lower()
