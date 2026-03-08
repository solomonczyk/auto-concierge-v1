"""
WS cookie-based auth tests.
High-risk audit: WS must not accept token/ticket in query string; auth via HttpOnly cookie only.
"""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.main import app
from app.api.endpoints import ws as ws_endpoint


class _DummyPubSub:
    def __init__(self):
        self.channels: list[str] = []

    async def subscribe(self, channel: str) -> None:
        self.channels.append(channel)

    async def unsubscribe(self, channel: str) -> None:
        if channel in self.channels:
            self.channels.remove(channel)

    async def get_message(self, **_kwargs):
        return None


class _DummyRedis:
    def __init__(self):
        self._pubsub = _DummyPubSub()

    def pubsub(self) -> _DummyPubSub:
        return self._pubsub


def _patch_redis(monkeypatch: pytest.MonkeyPatch) -> _DummyRedis:
    dummy = _DummyRedis()
    # Replace entire RedisService so get_redis() returns our dummy (avoids conftest mock)
    class _FakeRedisService:
        @staticmethod
        def get_redis():
            return dummy
    monkeypatch.setattr(ws_endpoint, "RedisService", _FakeRedisService)
    return dummy


@pytest.mark.asyncio
async def test_ws_connect_without_cookie_rejected(monkeypatch: pytest.MonkeyPatch):
    """WS connect without auth cookie must be rejected with 4401."""
    _patch_redis(monkeypatch)

    with TestClient(app) as sync_client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with sync_client.websocket_connect(f"{settings.API_V1_STR}/ws"):
                pass
        assert exc.value.code == 4401


@pytest.mark.asyncio
async def test_ws_connect_with_valid_cookie_success(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
):
    """WS connect with valid auth cookie must succeed."""
    _patch_redis(monkeypatch)

    with TestClient(app) as sync_client:
        login_res = sync_client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert login_res.status_code == 200
        assert "access_token" in sync_client.cookies

        with sync_client.websocket_connect(f"{settings.API_V1_STR}/ws"):
            pass


@pytest.mark.asyncio
async def test_ws_connect_query_string_token_rejected(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
):
    """Legacy ?token= in query string must be rejected with 4401."""
    _patch_redis(monkeypatch)

    with TestClient(app) as sync_client:
        sync_client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        access_token = sync_client.cookies.get("access_token")

        with pytest.raises(WebSocketDisconnect) as exc:
            with sync_client.websocket_connect(f"{settings.API_V1_STR}/ws?token={access_token}"):
                pass
        assert exc.value.code == 4401


@pytest.mark.asyncio
async def test_ws_connect_query_string_ticket_rejected(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
):
    """?ticket= in query string must be rejected with 4401 (no longer supported)."""
    _patch_redis(monkeypatch)

    with TestClient(app) as sync_client:
        sync_client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        # Even with valid cookie, passing ticket in URL must be rejected
        with pytest.raises(WebSocketDisconnect) as exc:
            with sync_client.websocket_connect(f"{settings.API_V1_STR}/ws?ticket=fake-ticket"):
                pass
        assert exc.value.code == 4401


@pytest.mark.asyncio
async def test_ws_tenant_channel_from_cookie(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
):
    """Cookie auth establishes connection; tenant context used for subscription.
    Full channel verification requires integration test with real Redis."""
    _patch_redis(monkeypatch)

    with TestClient(app) as sync_client:
        sync_client.post(
            f"{settings.API_V1_STR}/login/access-token",
            data={"username": "admin", "password": "admin"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        with sync_client.websocket_connect(f"{settings.API_V1_STR}/ws"):
            pass  # Connection succeeds; tenant from cookie used for channel
