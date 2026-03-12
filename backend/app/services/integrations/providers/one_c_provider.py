"""
1C integration provider. Sends appointment data to 1C API.
"""
import logging
from typing import Dict, Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def sync_to_1c(payload: Dict[str, Any], integration_settings: Dict[str, Any]) -> bool:
    """POST appointment payload to 1C endpoint. Returns True on success (2xx)."""
    endpoint = integration_settings.get("url", "https://mock-1c-api.ru/sync")
    timeout = settings.EXTERNAL_INTEGRATION_TIMEOUT_SECONDS

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, json=payload)
        if response.status_code >= 200 and response.status_code < 300:
            logger.info("1C sync success: appointment_id=%s", payload.get("external_id"))
            return True
        logger.warning("1C sync non-2xx: status=%s", response.status_code)
        return False
    except Exception as e:
        logger.error("1C sync failed: %s", e)
        raise
