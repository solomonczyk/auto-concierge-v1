"""
Integration test: PATCH /appointments/{id}/status → WebSocket client receives event.

Requires real Redis (testcontainers or docker-compose up -d redis).
Run: pytest tests/integration/test_patch_status_ws_e2e.py -v
"""
import json
import threading
import time
from queue import Queue, Empty

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, Client

from app.core.config import settings
from app.main import app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_patch_status_ws_receives_event_e2e(
    client_auth,
    db_session,
    reset_redis_pool,
):
    """
    Full E2E: create appointment → open WS → PATCH status → WS receives event.
    Verifies real Redis pub/sub path.
    """
    # 1. Create appointment with the authenticated client
    create_res = await client_auth.post(
        f"{settings.API_V1_STR}/appointments/",
        json={
            "service_id": 1,
            "start_time": "2026-03-25T22:00:00",
            "client_name": "WS E2E Client",
            "client_phone": "+79991114444",
        },
    )
    assert create_res.status_code == 200
    appt_id = create_res.json()["id"]

    # 2. Reuse the same authenticated session for WS cookie auth and PATCH CSRF
    cookies = {c.name: c.value for c in client_auth.cookies.jar}
    csrf_token = client_auth.cookies.get("csrf_token")
    assert csrf_token

    # 3. PATCH in background thread; WS receive in main (TestClient works in main thread)
    received_queue: Queue = Queue()
    patch_status: list = []
    ws_url = f"{settings.API_V1_STR}/ws"

    def do_patch():
        import asyncio
        from httpx import AsyncClient
        transport = ASGITransport(app=app)
        async def _patch():
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                ac.cookies.update(cookies)
                return await ac.patch(
                    f"{settings.API_V1_STR}/appointments/{appt_id}/status",
                    json={"status": "confirmed"},
                    headers={"X-CSRF-Token": csrf_token},
                )
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            r = loop.run_until_complete(_patch())
            patch_status.append(r.status_code)
        finally:
            loop.close()

    def run_patch_after_delay():
        time.sleep(1.5)
        do_patch()

    patch_thread = threading.Thread(target=run_patch_after_delay)
    patch_thread.start()

    # Reset Redis pool so WS handler creates connection in its own event loop
    from app.services.redis_service import RedisService
    RedisService._pool = None

    # 4. WS connect (cookie auth) and receive (main thread)
    with TestClient(app) as sync_client:
        for name, value in cookies.items():
            sync_client.cookies.set(name, value)
        with sync_client.websocket_connect(ws_url) as ws:
            msg = ws.receive_text()
            received_queue.put(msg)

    patch_thread.join(timeout=5)
    assert patch_status and patch_status[0] == 200, f"PATCH failed: {patch_status}"

    # 5. Get WS message and assert payload
    try:
        raw_msg = received_queue.get(timeout=2)
    except Empty:
        pytest.fail("WS did not receive message")

    if isinstance(raw_msg, dict) and "error" in raw_msg:
        pytest.fail(f"WS receiver error: {raw_msg['error']}")

    payload = json.loads(raw_msg)
    assert payload["type"] == "appointment_status_updated"
    assert payload.get("appointment_id") == appt_id or payload.get("id") == appt_id
    assert payload["old_status"] == "new"
    assert payload["new_status"] == "confirmed"
