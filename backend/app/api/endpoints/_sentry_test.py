"""
Temporary test endpoint for Sentry verification.
GET /api/v1/_sentry-test — raises ValueError to confirm events reach Sentry
with tenant_id tag and no sensitive data. Requires auth.
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.context import tenant_id_context

router = APIRouter()


@router.get("/_sentry-test")
async def sentry_test(
    current_user=Depends(get_current_user),
):
    """
    Raises ValueError to verify Sentry capture.
    Only available when SENTRY_DSN is set and ENVIRONMENT is development/test.
    Disabled in production — returns 404.
    """
    from fastapi import HTTPException

    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")

    if not getattr(settings, "SENTRY_DSN", None):
        raise ValueError("SENTRY_DSN not configured — test disabled")

    import sentry_sdk

    tenant_id = tenant_id_context.get()
    sentry_sdk.set_tag("tenant_id", str(tenant_id) if tenant_id is not None else "none")

    raise ValueError("Sentry test: intentional error for verification")
