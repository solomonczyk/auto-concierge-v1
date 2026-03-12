import logging
from typing import Optional, Dict, Any

from app.models.models import Appointment, Tenant
from app.core.config import settings
from app.services.redis_service import RedisService

logger = logging.getLogger(__name__)

from redis import Redis
from rq import Queue
from app.db.session import async_session_local
from sqlalchemy import select
from sqlalchemy.orm import joinedload
import asyncio

from app.services.integrations.providers import sync_to_1c, sync_to_alpha_auto

CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_KEY_PREFIX = "integration_failures:"


async def _check_circuit_breaker_open(tenant_id: int) -> bool:
    """Return True if circuit is open (>= threshold consecutive failures). Skip sync."""
    try:
        redis = RedisService.get_redis()
        key = f"{CIRCUIT_BREAKER_KEY_PREFIX}{tenant_id}"
        count = await redis.get(key)
        if count is None:
            return False
        return int(count) >= CIRCUIT_BREAKER_THRESHOLD
    except Exception as e:
        logger.warning("Circuit breaker check failed, allowing sync: %s", e)
        return False


async def _record_integration_failure(tenant_id: int) -> None:
    """Increment consecutive failure count for tenant."""
    try:
        redis = RedisService.get_redis()
        key = f"{CIRCUIT_BREAKER_KEY_PREFIX}{tenant_id}"
        await redis.incr(key)
    except Exception as e:
        logger.warning("Circuit breaker record failure: %s", e)


async def _record_integration_success(tenant_id: int) -> None:
    """Reset consecutive failure count on success."""
    try:
        redis = RedisService.get_redis()
        key = f"{CIRCUIT_BREAKER_KEY_PREFIX}{tenant_id}"
        await redis.delete(key)
    except Exception as e:
        logger.warning("Circuit breaker reset on success: %s", e)


class ExternalIntegrationService:
    """
    Standardized service for external integrations (1C, Alpha-Auto, etc.).
    Follows a hook-based architecture.
    """

    @staticmethod
    async def sync_appointment(appointment_id: int, tenant_id: int) -> tuple[bool, Optional[str]]:
        """Attempt external sync immediately and return a fail-safe result."""
        try:
            if await _check_circuit_breaker_open(tenant_id):
                logger.warning("Integration temporarily disabled for tenant %s (circuit breaker)", tenant_id)
                return False, "integration temporarily disabled"

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

                ok, err = await ExternalIntegrationService._sync_data(appt, tenant)
                if ok:
                    await _record_integration_success(tenant_id)
                else:
                    await _record_integration_failure(tenant_id)
                return ok, err
        except Exception as exc:
            logger.error(
                "integration.sync_exception appointment=%s tenant=%s: %s",
                appointment_id,
                tenant_id,
                exc,
            )
            await _record_integration_failure(tenant_id)
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
        if await _check_circuit_breaker_open(tenant_id):
            logger.warning("Integration temporarily disabled for tenant %s (circuit breaker)", tenant_id)
            return False

        async with async_session_local() as db:
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
                await _record_integration_failure(tenant_id)
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
                await _record_integration_failure(tenant_id)
                return False

            ok, _ = await ExternalIntegrationService._sync_data(appt, tenant)
            if ok:
                await _record_integration_success(tenant_id)
            else:
                await _record_integration_failure(tenant_id)
            return ok

    @staticmethod
    async def _sync_data(appointment: Appointment, tenant: Tenant) -> tuple[bool, Optional[str]]:
        integration_settings = tenant.settings_json.get("integration", {})
        integration_type = integration_settings.get("type", "none")

        if not integration_type or integration_type == "none":
            logger.info("No external integration configured for Tenant %s", tenant.id)
            return True, None

        payload = {
            "external_id": f"AC-{appointment.id}",
            "idempotency_key": f"appt-{appointment.id}",
            "client_name": "Syncing...",
            "start_time": appointment.start_time.isoformat(),
        }

        try:
            if integration_type == "1c":
                ok = await sync_to_1c(payload, integration_settings)
                return ok, None if ok else "1C sync returned unsuccessful result"
            elif integration_type == "alpha-auto":
                ok = await sync_to_alpha_auto(payload, integration_settings)
                return ok, None if ok else "Alpha Auto sync returned unsuccessful result"
            return False, f"Unsupported integration type: {integration_type}"
        except Exception as e:
            logger.error("Sync failed: %s", e)
            return False, str(e)[:500]


external_integration = ExternalIntegrationService()
