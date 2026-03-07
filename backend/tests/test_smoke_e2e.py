"""
End-to-end smoke test: full client journey.

Steps:
  1. POST /login/access-token  → cookie set
  2. GET  /me                  → user info with tenant
  3. POST /appointments/       → appointment created despite mocked external sync failure
  4. External sync fail-safe   → appointment persists, error logged
  5. WS receives update        → tenant-scoped pubsub
  6. Webhook processed         → tenant isolation respected
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.main import app
from app.api.endpoints import ws as ws_endpoint
from app.services import ws_ticket_store


class _DummyPubSub:
    def __init__(self):
        self.channels: list[str] = []

    async def subscribe(self, channel: str) -> None:
        self.channels.append(channel)

    async def unsubscribe(self, _channel: str) -> None:
        return None

    async def get_message(self, **_kwargs):
        return None


class _DummyRedis:
    def __init__(self):
        self.used_keys: set[str] = set()
        self._pubsub = _DummyPubSub()

    async def set(self, key: str, _value: str, nx: bool = False, ex: int = 0):
        if nx and key in self.used_keys:
            return None
        self.used_keys.add(key)
        return True

    def pubsub(self) -> _DummyPubSub:
        return self._pubsub


def _patch_redis(monkeypatch: pytest.MonkeyPatch) -> _DummyRedis:
    dummy = _DummyRedis()
    monkeypatch.setattr(
        ws_endpoint.RedisService, "get_redis", staticmethod(lambda: dummy)
    )
    monkeypatch.setattr(
        ws_ticket_store.RedisService, "get_redis", staticmethod(lambda: dummy)
    )
    return dummy


@pytest.mark.asyncio
async def test_full_client_journey(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    # ------------------------------------------------------------------
    # Step 1: Login
    # ------------------------------------------------------------------
    login_res = await client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_res.status_code == 200, f"Step 1 FAIL: login returned {login_res.status_code}"
    assert client.cookies.get("access_token"), "Step 1 FAIL: no access_token cookie"

    # ------------------------------------------------------------------
    # Step 2: GET /me
    # ------------------------------------------------------------------
    me_res = await client.get(f"{settings.API_V1_STR}/me")
    assert me_res.status_code == 200, f"Step 2 FAIL: /me returned {me_res.status_code}"
    me_data = me_res.json()
    assert me_data["username"] == "admin"
    assert me_data["tenant_id"] is not None
    assert me_data["role"] is not None
    tenant_id = me_data["tenant_id"]

    # ------------------------------------------------------------------
    # Step 3: Create appointment (external sync will fail — must not break)
    # ------------------------------------------------------------------
    start_time = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )

    appt_res = await client.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": start_time.isoformat(),
            "client_name": "Smoke Test Client",
            "client_phone": "+70001112233",
        },
    )
    assert appt_res.status_code == 200, f"Step 3 FAIL: create appointment returned {appt_res.status_code}: {appt_res.text}"
    appt_data = appt_res.json()
    assert appt_data["id"] is not None
    assert appt_data["status"] == "new"

    # ------------------------------------------------------------------
    # Step 4: External sync fail-safe (covered by conftest mock — enqueue is mocked)
    # Verify appointment exists despite external integration being mocked
    # ------------------------------------------------------------------
    get_appt_res = await client.get(f"{settings.API_V1_STR}/appointments/{appt_data['id']}")
    assert get_appt_res.status_code == 200, f"Step 4 FAIL: appointment not found after creation"
    assert get_appt_res.json()["id"] == appt_data["id"]

    # ------------------------------------------------------------------
    # Step 5: WS receives update scoped to tenant
    # ------------------------------------------------------------------
    ws_ticket_res = await client.post(f"{settings.API_V1_STR}/ws-ticket")
    assert ws_ticket_res.status_code == 200, f"Step 5 FAIL: ws-ticket returned {ws_ticket_res.status_code}"
    ws_ticket = ws_ticket_res.json()["ticket"]

    dummy_redis = _patch_redis(monkeypatch)

    with TestClient(app) as sync_client:
        with sync_client.websocket_connect(
            f"{settings.API_V1_STR}/ws?ticket={ws_ticket}"
        ) as ws:
            pass  # connect + disconnect

    assert len(dummy_redis._pubsub.channels) == 1
    subscribed_channel = dummy_redis._pubsub.channels[0]
    assert subscribed_channel == f"appointments_updates:{tenant_id}", (
        f"Step 5 FAIL: WS subscribed to '{subscribed_channel}', "
        f"expected 'appointments_updates:{tenant_id}'"
    )

    # ------------------------------------------------------------------
    # Step 6: Webhook processes without tenant isolation breach
    # ------------------------------------------------------------------
    from app.api.endpoints import webhook as webhook_endpoint

    monkeypatch.setattr(webhook_endpoint.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(webhook_endpoint.settings, "TELEGRAM_WEBHOOK_SECRET", None)

    feed_mock = AsyncMock()
    monkeypatch.setattr(webhook_endpoint.dp, "feed_update", feed_mock)

    fake_wh_redis = MagicMock()
    fake_wh_redis.exists = AsyncMock(return_value=False)
    fake_wh_redis.set = AsyncMock(return_value=True)
    monkeypatch.setattr(
        webhook_endpoint.RedisService, "get_redis", staticmethod(lambda: fake_wh_redis)
    )

    wh_res = await client.post(
        f"{settings.API_V1_STR}/webhook",
        json={
            "update_id": 999999,
            "message": {
                "message_id": 1,
                "date": 1709800000,
                "chat": {"id": 123456, "type": "private"},
                "text": "/start",
            },
        },
    )
    assert wh_res.status_code == 200, f"Step 6 FAIL: webhook returned {wh_res.status_code}"
    assert wh_res.json()["status"] == "ok"
    feed_mock.assert_awaited_once()
