import logging
import httpx
from typing import Optional, Dict, Any
from app.models.models import Appointment, Tenant
from app.core.config import settings

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
    async def sync_appointment(appointment_id: int, tenant_id: int) -> tuple[bool, Optional[str]]:
        """Attempt external sync immediately and return a fail-safe result."""
        try:
            async with async_session_local() as db:
                stmt_appt = select(Appointment).options(joinedload(Appointment.service)).where(Appointment.id == appointment_id)
                appt = (await db.execute(stmt_appt)).scalar_one_or_none()

                stmt_tenant = select(Tenant).where(Tenant.id == tenant_id)
                tenant = (await db.execute(stmt_tenant)).scalar_one_or_none()

                if not appt or not tenant:
                    message = f"appointment_or_tenant_not_found appointment={appointment_id} tenant={tenant_id}"
                    logger.error(
                        "integration.sync_not_found appointment=%s tenant=%s",
                        appointment_id,
                        tenant_id,
                    )
                    return False, message

                if appt.tenant_id != tenant_id:
                    message = f"tenant_mismatch owner={appt.tenant_id} requested={tenant_id}"
                    logger.error(
                        "integration.tenant_mismatch appointment=%s owner=%s requested=%s",
                        appointment_id,
                        appt.tenant_id,
                        tenant_id,
                    )
                    return False, message

                return await ExternalIntegrationService._sync_data(appt, tenant)
        except Exception as exc:
            logger.error(
                "integration.sync_exception appointment=%s tenant=%s: %s",
                appointment_id,
                tenant_id,
                exc,
            )
            return False, str(exc)[:500]

    @staticmethod
    def enqueue_appointment(appointment_id: int, tenant_id: int) -> bool:
        """
        Hardened: enqueue sync task to persistent Redis queue.
        Never raises to caller - failures are logged and ignored.
        """
        try:
            redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}"
            q = Queue("default", connection=Redis.from_url(redis_url))
            q.enqueue(
                ExternalIntegrationService.run_sync_job,
                appointment_id,
                tenant_id,
                retry=3,  # Hardened: automatic retries
            )
            return True
        except Exception as exc:
            logger.error(
                "Failed to enqueue external sync for appointment=%s tenant=%s: %s",
                appointment_id,
                tenant_id,
                exc,
            )
            return False

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
                logger.error(
                    "integration.sync_not_found appointment=%s tenant=%s",
                    appointment_id,
                    tenant_id,
                    extra={
                        "event_type": "integration_failure",
                        "tenant_id": tenant_id,
                    },
                )
                return False

            if appt.tenant_id != tenant_id:
                logger.error(
                    "integration.tenant_mismatch appointment=%s owner=%s requested=%s",
                    appointment_id,
                    appt.tenant_id,
                    tenant_id,
                    extra={
                        "event_type": "tenant_isolation_reject",
                        "tenant_id": tenant_id,
                    },
                )
                return False
                
            ok, _ = await ExternalIntegrationService._sync_data(appt, tenant)
            return ok

    @staticmethod
    async def _sync_data(appointment: Appointment, tenant: Tenant) -> tuple[bool, Optional[str]]:
        # 1. Fetch Integration Settings
        integration_settings = tenant.settings_json.get("integration", {})
        integration_type = integration_settings.get("type", "none")
        
        if not integration_type or integration_type == "none":
            logger.info(f"No external integration configured for Tenant {tenant.id}")
            return True, None

        # 2. Prepare Payload
        # appointment.client and appointment.service might not be loaded if called from background
        payload = {
            "external_id": f"AC-{appointment.id}",
            "client_name": "Syncing...", # Real implementation would ensure these are loaded or use IDs
            "start_time": appointment.start_time.isoformat(),
        }

        try:
            if integration_type == "1c":
                ok = await ExternalIntegrationService._sync_to_1c(payload, integration_settings)
                return ok, None if ok else "1C sync returned unsuccessful result"
            elif integration_type == "alpha-auto":
                ok = await ExternalIntegrationService._sync_to_alpha_auto(payload, integration_settings)
                return ok, None if ok else "Alpha Auto sync returned unsuccessful result"
            return False, f"Unsupported integration type: {integration_type}"
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return False, str(e)[:500]

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
