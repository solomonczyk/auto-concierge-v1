from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.redis_service import RedisService
import asyncio
import logging
from jose import jwt, JWTError
from app.core.config import settings
from sqlalchemy import select
from app.db.session import async_session_local
from app.models.models import User
from app.services.ws_ticket_service import validate_ws_ticket, WSTicketValidationError
from app.services.ws_ticket_store import consume_jti_once
from datetime import datetime, timezone

router = APIRouter()
logger = logging.getLogger(__name__)
ws_legacy_auth_total = 0


def _increment_legacy_ws_auth_total() -> int:
    global ws_legacy_auth_total
    ws_legacy_auth_total += 1
    return ws_legacy_auth_total

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    ticket = websocket.query_params.get("ticket")
    token = websocket.query_params.get("token")
    tenant_id = None
    ws_auth_context: dict[str, str | int | None] = {}

    if ticket:
        try:
            claims = validate_ws_ticket(ticket=ticket)
            exp = claims.get("exp")
            now_ts = int(datetime.now(timezone.utc).timestamp())
            remaining_ttl = int(exp) - now_ts if exp is not None else 0
            jti = claims.get("jti")
            if not await consume_jti_once(jti=jti, ttl_seconds=remaining_ttl):
                await websocket.close(code=4403)
                return

            tenant_id = claims.get("tenant_id")
            ws_auth_context = {
                "auth_type": "ticket",
                "user_id": claims.get("user_id"),
                "tenant_id": claims.get("tenant_id"),
                "role": claims.get("role"),
                "jti": jti,
            }
        except WSTicketValidationError:
            await websocket.close(code=4401)
            return

    # Temporary fallback: keep legacy ?token=... while ws-ticket rollout is in progress.
    if tenant_id is None:
        if not token:
            await websocket.close(code=4401)
            return

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            tenant_id = payload.get("tenant_id")
            username = payload.get("sub")
            ws_auth_context = {
                "auth_type": "legacy_token_ws",
                "user_id": None,
                "tenant_id": tenant_id,
                "role": payload.get("role"),
                "jti": None,
            }
        except JWTError:
            await websocket.close(code=4401)
            return

        if not tenant_id:
            if not username:
                await websocket.close(code=4401)
                return
            async with async_session_local() as db:
                result = await db.execute(select(User).where(User.username == username))
                user = result.scalar_one_or_none()
                if not user:
                    await websocket.close(code=4401)
                    return
                tenant_id = user.tenant_id
                ws_auth_context["user_id"] = user.id
                ws_auth_context["tenant_id"] = user.tenant_id
                ws_auth_context["role"] = user.role.value if user.role else None

        metric_value = _increment_legacy_ws_auth_total()
        logger.warning(
            "WS legacy auth used (?token=...). This path is deprecated.",
            extra={
                "user_id": ws_auth_context.get("user_id"),
                "tenant_id": tenant_id,
                "auth_type": ws_auth_context.get("auth_type"),
                "metric_name": "ws_legacy_auth_total",
                "metric_value": metric_value,
            },
        )

    if tenant_id is None:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    websocket.state.auth_context = ws_auth_context
    redis = RedisService.get_redis()
    pubsub = redis.pubsub()
    channel_name = f"appointments_updates:{tenant_id}"
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
            # Keep connection open, ignore incoming messages from client for now
            # In a real chat app we would broadcast them
            await websocket.receive_text()
    except WebSocketDisconnect:
        task.cancel()
        await pubsub.unsubscribe(channel_name)
