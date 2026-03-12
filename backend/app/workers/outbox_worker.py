import asyncio
import logging

from app.db.session import async_session_local
from app.services.outbox_service import run_outbox_once

logger = logging.getLogger(__name__)


async def run_outbox_worker(
    *,
    poll_interval_seconds: float = 2.0,
    batch_limit: int = 100,
) -> None:
    while True:
        try:
            async with async_session_local() as db:
                await run_outbox_once(db, limit=batch_limit)
        except Exception as exc:
            logger.exception("Outbox worker iteration failed: %s", exc)

        await asyncio.sleep(poll_interval_seconds)
