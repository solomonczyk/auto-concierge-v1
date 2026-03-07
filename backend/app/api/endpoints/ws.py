from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.redis_service import RedisService
from app.services.ws_auth_resolver import (
    resolve_ws_auth_from_cookie,
    _extract_cookie_from_scope,
    WSAuthError,
)
from app.api.deps import AUTH_COOKIE_NAME
from app.core.metrics import (
    WS_CONNECTIONS_TOTAL,
    WS_DISCONNECT_TOTAL,
    WS_AUTH_REJECTED_TOTAL,
    WS_ACTIVE_CONNECTIONS,
)
import asyncio
import logging
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

_CLOSE_REASON_MAP = {
    4401: "no_cookie",
    4403: "replay",
}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    correlation_id = f"ws_{uuid.uuid4().hex[:12]}"

    # Reject query-string auth: token/ticket in URL is a security risk
    if websocket.query_params.get("token") or websocket.query_params.get("ticket"):
        WS_AUTH_REJECTED_TOTAL.labels(reason="query_auth_rejected").inc()
        logger.info(
            "ws.auth_reject reason=query_auth_rejected",
            extra={"correlation_id": correlation_id},
        )
        await websocket.close(code=4401)
        return

    cookie_token = _extract_cookie_from_scope(websocket.scope, AUTH_COOKIE_NAME)
    try:
        auth_context = await resolve_ws_auth_from_cookie(cookie_token=cookie_token)
    except WSAuthError as exc:
        reason = _CLOSE_REASON_MAP.get(exc.close_code, "invalid_ticket")
        WS_AUTH_REJECTED_TOTAL.labels(reason=reason).inc()
        logger.info(
            "ws.auth_reject reason=%s",
            reason,
            extra={"correlation_id": correlation_id},
        )
        await websocket.close(code=exc.close_code)
        return

    await websocket.accept()
    websocket.state.auth_context = auth_context

    tenant_id = str(auth_context.tenant_id)
    WS_CONNECTIONS_TOTAL.labels(tenant_id=tenant_id).inc()
    WS_ACTIVE_CONNECTIONS.labels(tenant_id=tenant_id).inc()
    logger.info(
        "ws.connect tenant_id=%s",
        tenant_id,
        extra={"correlation_id": correlation_id, "tenant_id": auth_context.tenant_id},
    )

    redis = RedisService.get_redis()
    pubsub = redis.pubsub()
    channel_name = f"appointments_updates:{auth_context.tenant_id}"
    await pubsub.subscribe(channel_name)

    async def reader():
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    await websocket.send_text(message["data"])
                await asyncio.sleep(0.1)
        except Exception:
            pass

    task = asyncio.create_task(reader())

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        WS_DISCONNECT_TOTAL.labels(tenant_id=tenant_id).inc()
        WS_ACTIVE_CONNECTIONS.labels(tenant_id=tenant_id).dec()
        logger.info(
            "ws.disconnect tenant_id=%s",
            tenant_id,
            extra={"correlation_id": correlation_id, "tenant_id": int(tenant_id)},
        )
        task.cancel()
        await pubsub.unsubscribe(channel_name)
