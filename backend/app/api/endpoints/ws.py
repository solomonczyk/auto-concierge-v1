from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.redis_service import RedisService
from app.services.ws_auth_resolver import resolve_ws_auth, WSAuthError
import asyncio
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    ticket = websocket.query_params.get("ticket")

    try:
        auth_context = await resolve_ws_auth(ticket=ticket)
    except WSAuthError as exc:
        await websocket.close(code=exc.close_code)
        return

    await websocket.accept()
    websocket.state.auth_context = auth_context
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
        task.cancel()
        await pubsub.unsubscribe(channel_name)
