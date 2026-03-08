"""
Integration tests conftest: real Redis, no mocks.

Redis must be running:
  docker-compose up -d redis
  # or: testcontainers spawns Redis automatically (requires Docker)
"""
import os
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import patch
from threading import Thread
from queue import Queue
import time

# Ensure we load before parent conftest's app import
import app.core.config as config_module

# Parent tests/conftest.py is auto-loaded by pytest when running tests/integration/


@pytest.fixture(autouse=True)
def mock_redis_notifications_ratelimit():
    """Override parent: use real Redis, but still mock NotificationService and external_integration."""
    from unittest.mock import AsyncMock

    with patch("app.services.notification_service.NotificationService.send_booking_confirmation", new_callable=AsyncMock):
        with patch("app.services.notification_service.NotificationService.notify_admin", new_callable=AsyncMock):
            with patch("app.services.notification_service.NotificationService.notify_client_status_change", new_callable=AsyncMock):
                with patch("app.api.endpoints.appointments.external_integration.enqueue_appointment", new_callable=AsyncMock):
                    yield


@pytest.fixture(scope="session")
def redis_container():
    """Start Redis via testcontainers. Skip if Docker unavailable."""
    try:
        from testcontainers.redis import RedisContainer

        with RedisContainer("redis:7-alpine") as redis:
            host = redis.get_container_host_ip()
            port = int(redis.get_exposed_port(6379))
            yield host, port
    except Exception as e:
        pytest.skip(
            f"Redis container failed (Docker required): {e}. "
            "Alternative: run 'docker-compose up -d redis' and set REDIS_HOST=localhost"
        )


@pytest.fixture(scope="session")
def integration_settings(redis_container):
    """Patch settings to use test Redis before app uses it."""
    host, port = redis_container
    orig_host = getattr(config_module.settings, "REDIS_HOST", None)
    orig_port = getattr(config_module.settings, "REDIS_PORT", None)
    config_module.settings.REDIS_HOST = host
    config_module.settings.REDIS_PORT = port
    yield config_module.settings
    if orig_host is not None:
        config_module.settings.REDIS_HOST = orig_host
    if orig_port is not None:
        config_module.settings.REDIS_PORT = orig_port


@pytest.fixture(scope="function")
def reset_redis_pool(integration_settings):
    """Reset RedisService pool so it reconnects to test Redis."""
    from app.services.redis_service import RedisService

    RedisService._pool = None
    yield
    # Cleanup after test
    async def _close():
        await RedisService.close()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_close())
        else:
            loop.run_until_complete(_close())
    except Exception:
        pass
    RedisService._pool = None
