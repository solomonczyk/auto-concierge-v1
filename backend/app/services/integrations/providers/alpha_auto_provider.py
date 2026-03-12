"""
Alpha-Auto integration provider. Sends appointment data to Alpha-Auto API.
"""
import logging
from typing import Dict, Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def sync_to_alpha_auto(payload: Dict[str, Any], integration_settings: Dict[str, Any]) -> bool:
    """POST appointment payload to Alpha-Auto endpoint. Returns True on success (2xx)."""
    endpoint = integration_settings.get("url", "https://mock-alpha-auto.ru/api")
    timeout = settings.EXTERNAL_INTEGRATION_TIMEOUT_SECONDS

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, json=payload)
        if response.status_code >= 200 and response.status_code < 300:
            logger.info("Alpha-Auto sync success: appointment_id=%s", payload.get("external_id"))
            return True
        logger.warning("Alpha-Auto sync non-2xx: status=%s", response.status_code)
        return False
    except Exception as e:
        logger.error("Alpha-Auto sync failed: %s", e)
        raise
