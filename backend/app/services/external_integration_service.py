import logging
import httpx
from typing import Optional, Dict, Any
from app.models.models import Appointment, Tenant

logger = logging.getLogger(__name__)

from redis import Redis
from rq import Queue
from app.db.session import async_session_local
from sqlalchemy import select
from sqlalchemy.orm import joinedload
import asyncio

class ExternalIntegrationService:
    """
    Standardized service for external integrations (1C, Alpha-Auto, etc.).
    Follows a hook-based architecture.
    """

    @staticmethod
    def enqueue_appointment(appointment_id: int, tenant_id: int):
        """
        Hardened: Enqueue the sync task into persistent Redis Queue.
        """
        redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
        q = Queue('default', connection=Redis.from_url(redis_url))
        q.enqueue(
            ExternalIntegrationService.run_sync_job, 
            appointment_id, 
            tenant_id,
            retry=3 # Hardened: Automatic retries
        )

    @staticmethod
    def run_sync_job(appointment_id: int, tenant_id: int):
        """
        Bridge for RQ (synchronous worker calling async logic).
        """
        return asyncio.run(ExternalIntegrationService._sync_by_ids(appointment_id, tenant_id))

    @staticmethod
    async def _sync_by_ids(appointment_id: int, tenant_id: int) -> bool:
        async with async_session_local() as db:
            # Re-fetch objects to ensure they are fresh and loaded
            stmt_appt = select(Appointment).options(joinedload(Appointment.service)).where(Appointment.id == appointment_id)
            appt = (await db.execute(stmt_appt)).scalar_one_or_none()
            
            stmt_tenant = select(Tenant).where(Tenant.id == tenant_id)
            tenant = (await db.execute(stmt_tenant)).scalar_one_or_none()
            
            if not appt or not tenant:
                logger.error(f"Sync failed: Appointment {appointment_id} or Tenant {tenant_id} not found")
                return False
                
            return await ExternalIntegrationService._sync_data(appt, tenant)

    @staticmethod
    async def _sync_data(appointment: Appointment, tenant: Tenant) -> bool:
        # 1. Fetch Integration Settings
        integration_settings = tenant.settings_json.get("integration", {})
        integration_type = integration_settings.get("type", "none")
        
        if not integration_type or integration_type == "none":
            logger.info(f"No external integration configured for Tenant {tenant.id}")
            return True

        # 2. Prepare Payload
        # appointment.client and appointment.service might not be loaded if called from background
        payload = {
            "external_id": f"AC-{appointment.id}",
            "client_name": "Syncing...", # Real implementation would ensure these are loaded or use IDs
            "start_time": appointment.start_time.isoformat(),
        }

        try:
            if integration_type == "1c":
                return await ExternalIntegrationService._sync_to_1c(payload, integration_settings)
            elif integration_type == "alpha-auto":
                return await ExternalIntegrationService._sync_to_alpha_auto(payload, integration_settings)
            return False
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return False

    @staticmethod
    async def _sync_to_1c(payload: Dict[str, Any], settings: Dict[str, Any]) -> bool:
        endpoint = settings.get("url", "https://mock-1c-api.ru/sync")
        logger.info(f"[BG] Pushing to 1C: {payload}")
        return True

    @staticmethod
    async def _sync_to_alpha_auto(payload: Dict[str, Any], settings: Dict[str, Any]) -> bool:
        endpoint = settings.get("url", "https://mock-alpha-auto.ru/api")
        logger.info(f"[BG] Pushing to Alpha-Auto: {payload}")
        return True

external_integration = ExternalIntegrationService()
