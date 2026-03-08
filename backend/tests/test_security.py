"""
Security tests for Stage 1: cookie flags, rate limit, CORS.

- Cookie flags: auth cookie HttpOnly/SameSite, CSRF cookie not HttpOnly
- Rate limit: login/public booking 429 after limit exceeded
- CORS: no wildcard with credentials in production
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.endpoints import login as login_module
from app.core.config import settings
from app.core.rate_limit import LOGIN_RATE_LIMIT, PUBLIC_BOOKING_RATE_LIMIT
from app.main import app
from app.models.models import Tenant


def _get_set_cookie_headers(res) -> list:
    """Extract all Set-Cookie header values. TestClient (requests) uses res.raw.msg.get_all()."""
    if hasattr(res, "raw") and res.raw is not None and hasattr(res.raw, "msg") and res.raw.msg is not None:
        return list(res.raw.msg.get_all("Set-Cookie", []))
    if hasattr(res, "headers"):
        h = res.headers
        for getter in ("get_all", "getall"):
            if hasattr(h, getter):
                vals = getattr(h, getter)("set-cookie")
                if vals:
                    return list(vals) if not isinstance(vals, list) else vals
        if hasattr(h, "multi_items"):
            return [v for k, v in h.multi_items() if k.lower() == "set-cookie"]
        single = h.get("set-cookie") if hasattr(h, "get") else None
        return [single] if single else []
    return []


def _parse_set_cookie(header_value: str) -> dict:
    """Parse Set-Cookie header into dict of attr -> value."""
    parts = header_value.split(";")
    attrs = {}
    for p in parts[1:]:  # skip name=value
        p = p.strip()
        if "=" in p:
            k, v = p.split("=", 1)
            attrs[k.strip().lower()] = v.strip().lower()
        else:
            attrs[p.lower()] = "true"
    return attrs


@pytest.mark.asyncio
async def test_cookie_flags_auth_httponly_samesite(client: AsyncClient):
    """Auth cookie (access_token) must have HttpOnly and SameSite."""
    res = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200

    set_cookies = _get_set_cookie_headers(res)
    auth_header = next((h for h in set_cookies if h.startswith("access_token=")), None)
    assert auth_header, "Login must set access_token cookie"

    attrs = _parse_set_cookie(auth_header)
    assert attrs.get("httponly") in ("true", "1"), "Auth cookie must be HttpOnly"
    assert attrs.get("samesite") == "lax", "Auth cookie must have SameSite=Lax"


@pytest.mark.asyncio
async def test_cookie_flags_csrf_not_httponly(client: AsyncClient):
    """CSRF cookie must NOT be HttpOnly so frontend JS can read it."""
    res = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200

    set_cookies = _get_set_cookie_headers(res)
    csrf_header = next((h for h in set_cookies if h.startswith("csrf_token=")), None)
    assert csrf_header, "Login must set csrf_token cookie"

    attrs = _parse_set_cookie(csrf_header)
    assert attrs.get("httponly") not in ("true", "1"), "CSRF cookie must NOT be HttpOnly (JS needs to read it)"


@pytest.mark.asyncio
async def test_rate_limit_login_returns_429(client: AsyncClient):
    """Login endpoint returns 429 after exceeding its IP-based limit."""
    original = login_module.limiter.enabled
    login_module.limiter.enabled = True
    try:
        url = f"{settings.API_V1_STR}/login/access-token"
        data = {"username": "admin", "password": "admin"}
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "x-forwarded-for": "203.0.113.10",
        }
        limit_count = int(LOGIN_RATE_LIMIT.split("/")[0])

        for i in range(limit_count + 1):
            res = await client.post(url, data=data, headers=headers)
            if i < limit_count:
                assert res.status_code in (200, 400), f"Request {i+1}: expected 200 or 400, got {res.status_code}"
            else:
                assert res.status_code == 429, f"Request {limit_count + 1}: expected 429, got {res.status_code}"
                body = res.json()
                assert "too many requests" in body.get("detail", "").lower()
                assert body.get("error") == "rate_limit_exceeded"
                assert body.get("limit")
    finally:
        login_module.limiter.enabled = original


@pytest.mark.asyncio
async def test_rate_limit_public_booking_returns_429(client: AsyncClient, db_session: AsyncSession):
    """Public booking endpoint returns 429 after exceeding its IP-based limit."""
    original = login_module.limiter.enabled
    login_module.limiter.enabled = True
    try:
        tenant_result = await db_session.execute(select(Tenant).where(Tenant.id == 1))
        tenant = tenant_result.scalar_one()
        tenant.slug = "test-tenant"
        await db_session.commit()

        limit_count = int(PUBLIC_BOOKING_RATE_LIMIT.split("/")[0])
        headers = {"x-forwarded-for": "203.0.113.20"}
        booking_time = datetime.now(timezone.utc) + timedelta(days=1)

        for i in range(limit_count + 1):
            payload = {
                "service_id": 1,
                "date": booking_time.isoformat(),
                "telegram_id": 900000 + i,
                "full_name": f"Waitlist User {i}",
                "is_waitlist": True,
            }
            res = await client.post(
                "/api/v1/test-tenant/appointments/public",
                json=payload,
                headers=headers,
            )
            if i < limit_count:
                assert res.status_code == 200, f"Request {i+1}: expected 200, got {res.status_code}"
            else:
                assert res.status_code == 429, f"Request {limit_count + 1}: expected 429, got {res.status_code}"
                body = res.json()
                assert "too many requests" in body.get("detail", "").lower()
                assert body.get("error") == "rate_limit_exceeded"
                assert body.get("limit")
    finally:
        login_module.limiter.enabled = original


@pytest.mark.asyncio
async def test_cors_allows_trusted_origin(client: AsyncClient):
    """CORS allows credentials from trusted origin (localhost:5173)."""
    res = await client.get(
        "/",
        headers={"Origin": "http://localhost:5173"},
    )
    assert res.status_code == 200
    acao = res.headers.get("access-control-allow-origin")
    assert acao == "http://localhost:5173", f"Expected ACAO for trusted origin, got {acao}"


@pytest.mark.asyncio
async def test_cors_rejects_untrusted_origin(client: AsyncClient):
    """CORS does not allow untrusted origin (no ACAO or not wildcard)."""
    res = await client.get(
        "/",
        headers={"Origin": "http://evil.example.com"},
    )
    assert res.status_code == 200
    acao = res.headers.get("access-control-allow-origin")
    assert acao != "*", "Must not use wildcard with credentials"
    assert acao is None or acao != "http://evil.example.com", "Must not allow untrusted origin"


def test_cors_production_wildcard_raises():
    """With ENVIRONMENT=production and BACKEND_CORS_ORIGINS containing *, app fails at startup."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env["BACKEND_CORS_ORIGINS"] = "*"
    env["PYTHONPATH"] = backend_dir
    env.setdefault("POSTGRES_SERVER", "localhost")
    env.setdefault("POSTGRES_USER", "test")
    env.setdefault("POSTGRES_PASSWORD", "test")
    env.setdefault("POSTGRES_DB", "test")
    env.setdefault("REDIS_HOST", "localhost")

    result = subprocess.run(
        [sys.executable, "-c", "from app.main import app"],
        capture_output=True,
        text=True,
        cwd=backend_dir,
        env=env,
    )
    assert result.returncode != 0, "Expected startup failure with wildcard CORS in production"
    err = (result.stderr or result.stdout or "").lower()
    assert "wildcard" in err or "cors" in err, f"Expected CORS/wildcard error, got: {err[:500]}"
