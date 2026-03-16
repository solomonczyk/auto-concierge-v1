import logging
import time as time_module

from app.core.health_checks import HEALTH_CHECKS
from app.core.health_profiles import SERVICE_HEALTH_PROFILES

logger = logging.getLogger(__name__)


async def run_named_checks(check_names: list[str]) -> tuple[dict[str, str], float]:
    checks: dict[str, str] = {}
    start = time_module.monotonic()

    for name in check_names:
        check_fn = HEALTH_CHECKS.get(name)
        if check_fn is None:
            logger.error("[readiness] Unknown health check: %s", name)
            checks[name] = "unavailable: UnknownCheck"
            continue
        checks[name] = await check_fn()

    elapsed_ms = round((time_module.monotonic() - start) * 1000)
    return checks, elapsed_ms


async def run_service_readiness(service_name: str) -> tuple[dict[str, str], float]:
    check_names = SERVICE_HEALTH_PROFILES.get(service_name)
    if check_names is None:
        logger.error("[readiness] Unknown service profile: %s", service_name)
        return {"service": "unavailable: UnknownServiceProfile"}, 0
    return await run_named_checks(check_names)


async def run_readiness_checks() -> tuple[dict[str, str], float]:
    """Backward-compatible API readiness wrapper."""
    return await run_service_readiness("api")


