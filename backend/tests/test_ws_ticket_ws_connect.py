import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.main import app
from app.api.endpoints import ws as ws_endpoint
from app.services import ws_ticket_store, ws_auth_resolver


class _DummyPubSub:
    async def subscribe(self, _channel: str) -> None:
        return None

    async def unsubscribe(self, _channel: str) -> None:
        return None

    async def get_message(self, **_kwargs):
        return None


class _DummyRedis:
    def __init__(self):
        self.used_keys: set[str] = set()

    async def set(self, key: str, _value: str, nx: bool = False, ex: int = 0):
        if nx and key in self.used_keys:
            return None
        self.used_keys.add(key)
        return True

    def pubsub(self) -> _DummyPubSub:
        return _DummyPubSub()


def _patch_redis(monkeypatch: pytest.MonkeyPatch) -> _DummyRedis:
    """Patch Redis in all modules that use it."""
    dummy = _DummyRedis()
    monkeypatch.setattr(
        ws_endpoint.RedisService,
        "get_redis",
        staticmethod(lambda: dummy),
    )
    monkeypatch.setattr(
        ws_ticket_store.RedisService,
        "get_redis",
        staticmethod(lambda: dummy),
    )
    monkeypatch.setattr(
        ws_auth_resolver.consume_jti_once,
        "__module__",
        ws_auth_resolver.consume_jti_once.__module__,
    )
    return dummy


@pytest.mark.asyncio
async def test_ws_connect_with_ticket_success(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    login_response = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    ws_ticket_response = await client.post(
        f"{settings.API_V1_STR}/ws-ticket",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert ws_ticket_response.status_code == 200
    ws_ticket = ws_ticket_response.json()["ticket"]

    _patch_redis(monkeypatch)

    with TestClient(app) as sync_client:
        with sync_client.websocket_connect(f"{settings.API_V1_STR}/ws?ticket={ws_ticket}"):
            pass

        with pytest.raises(WebSocketDisconnect) as exc:
            with sync_client.websocket_connect(f"{settings.API_V1_STR}/ws?ticket={ws_ticket}"):
                pass
        assert exc.value.code == 4403


@pytest.mark.asyncio
async def test_ws_connect_without_ticket_returns_4401(
    monkeypatch: pytest.MonkeyPatch,
):
    """WS connect without any ticket must be rejected with 4401."""
    _patch_redis(monkeypatch)

    with TestClient(app) as sync_client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with sync_client.websocket_connect(f"{settings.API_V1_STR}/ws"):
                pass
        assert exc.value.code == 4401


@pytest.mark.asyncio
async def test_ws_connect_with_legacy_token_returns_4401(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Legacy ?token= must no longer be accepted — expect 4401."""
    login_response = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    _patch_redis(monkeypatch)

    with TestClient(app) as sync_client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with sync_client.websocket_connect(f"{settings.API_V1_STR}/ws?token={access_token}"):
                pass
        assert exc.value.code == 4401
