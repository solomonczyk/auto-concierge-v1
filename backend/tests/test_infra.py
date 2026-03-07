"""
Stage 2: Production infrastructure tests.

- /health, /live, /ready endpoints
- /ready reflects DB/Redis unavailability
- Production config fail-fast
"""
import os
import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_health_returns_success(client: AsyncClient):
    """GET /health returns 200 when deps are available."""
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "project" in data
    assert "checks" in data
    assert data["checks"].get("db") == "ok"
    assert data["checks"].get("redis") == "ok"


@pytest.mark.asyncio
async def test_live_returns_success(client: AsyncClient):
    """GET /live returns 200, no dependency checks."""
    res = await client.get("/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "project" in data


@pytest.mark.asyncio
async def test_ready_returns_success_when_deps_available(client: AsyncClient):
    """GET /ready returns 200 when DB and Redis are available."""
    res = await client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["checks"].get("db") == "ok"
    assert data["checks"].get("redis") == "ok"


@pytest.mark.asyncio
async def test_ready_reflects_db_unavailable(client: AsyncClient):
    """GET /ready returns 503 when DB is unavailable."""
    mock_sess = AsyncMock()
    mock_sess.execute = AsyncMock(side_effect=Exception("Connection refused"))

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_sess
    mock_cm.__aexit__.return_value = None

    with patch("app.db.session.async_session_local", return_value=mock_cm):
        res = await client.get("/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "not_ready"
    assert "db" in data["checks"]
    assert "unavailable" in data["checks"]["db"].lower() or "error" in data["checks"]["db"].lower()


@pytest.mark.asyncio
async def test_ready_reflects_redis_unavailable(client: AsyncClient):
    """GET /ready returns 503 when Redis is unavailable."""
    from app.services import redis_service as redis_mod

    original_get = redis_mod.RedisService.get_redis

    async def failing_ping():
        raise Exception("Connection refused")

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(side_effect=Exception("Connection refused"))

    with patch.object(redis_mod.RedisService, "get_redis", return_value=mock_redis):
        res = await client.get("/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert "redis" in data["checks"]
        assert "unavailable" in data["checks"]["redis"].lower() or "error" in data["checks"]["redis"].lower()


def test_production_config_fail_fast_missing_secret():
    """With ENVIRONMENT=production and SECRET_KEY missing/invalid, config fails at init."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env["SECRET_KEY"] = "dev-secret-key-change-in-production"
    env["TELEGRAM_WEBHOOK_SECRET"] = "test-secret"
    env["ENCRYPTION_KEY"] = "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODkwMTIzNDU2Nzg5MDE="
    env["PYTHONPATH"] = backend_dir
    env.setdefault("POSTGRES_SERVER", "localhost")
    env.setdefault("POSTGRES_USER", "test")
    env.setdefault("POSTGRES_PASSWORD", "test")
    env.setdefault("POSTGRES_DB", "test")
    env.setdefault("REDIS_HOST", "localhost")

    result = subprocess.run(
        [sys.executable, "-c", "from app.core.config import settings"],
        capture_output=True,
        text=True,
        cwd=backend_dir,
        env=env,
    )
    assert result.returncode != 0
    err = (result.stderr or result.stdout or "").lower()
    assert "secret_key" in err or "secret" in err


def test_production_config_fail_fast_missing_encryption_key():
    """With ENVIRONMENT=production and ENCRYPTION_KEY missing, config fails at init."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    env["SECRET_KEY"] = "prod-secret-key-at-least-32-chars-long"
    env["TELEGRAM_WEBHOOK_SECRET"] = "test-secret"
    env.pop("ENCRYPTION_KEY", None)
    env["PYTHONPATH"] = backend_dir
    env.setdefault("POSTGRES_SERVER", "localhost")
    env.setdefault("POSTGRES_USER", "test")
    env.setdefault("POSTGRES_PASSWORD", "test")
    env.setdefault("POSTGRES_DB", "test")
    env.setdefault("REDIS_HOST", "localhost")

    result = subprocess.run(
        [sys.executable, "-c", "from app.core.config import settings"],
        capture_output=True,
        text=True,
        cwd=backend_dir,
        env=env,
    )
    assert result.returncode != 0
    err = (result.stderr or result.stdout or "").lower()
    assert "encryption" in err
