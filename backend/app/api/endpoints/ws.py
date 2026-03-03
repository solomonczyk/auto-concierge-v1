from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.redis_service import RedisService
import asyncio
import json
from jose import jwt, JWTError
from app.core.config import settings
from sqlalchemy import select
from app.db.session import async_session_local
from app.models.models import User

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        tenant_id = payload.get("tenant_id")
        username = payload.get("sub")
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

    await websocket.accept()
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
