import logging
from datetime import datetime, timezone

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AUTH_COOKIE_NAME
from app.core.config import settings
from app.db.session import async_session_local
from app.models.models import User
from app.models.ws_auth_context import WSAuthContext
from app.services.ws_ticket_service import (
    validate_ws_ticket,
    WSTicketValidationError,
    WSTicketClaims,
)
from app.services.ws_ticket_store import consume_jti_once

logger = logging.getLogger(__name__)


class WSAuthError(Exception):
    """Raised when WS authentication fails."""

    def __init__(self, close_code: int):
        self.close_code = close_code


async def resolve_ws_auth(*, ticket: str | None) -> WSAuthContext:
    """Validate WS ticket and return typed auth context.

    Raises WSAuthError with appropriate WS close code on failure.
    """
    if not ticket:
        logger.warning(
            "ws_auth.no_ticket",
            extra={"event_type": "auth_reject", "auth_type": "ws_ticket"},
        )
        raise WSAuthError(close_code=4401)

    try:
        claims: WSTicketClaims = validate_ws_ticket(ticket=ticket)
    except WSTicketValidationError:
        logger.warning(
            "ws_auth.invalid_ticket",
            extra={"event_type": "auth_reject", "auth_type": "ws_ticket"},
        )
        raise WSAuthError(close_code=4401)

    now_ts = int(datetime.now(timezone.utc).timestamp())
    remaining_ttl = claims.exp - now_ts

    if not await consume_jti_once(jti=claims.jti, ttl_seconds=remaining_ttl):
        logger.warning(
            "ws_auth.replay user_id=%s jti=%s",
            claims.user_id,
            claims.jti,
            extra={
                "event_type": "security_warning",
                "auth_type": "ws_ticket",
                "user_id": claims.user_id,
                "tenant_id": claims.tenant_id,
            },
        )
        raise WSAuthError(close_code=4403)

    logger.info(
        "ws_auth.ok user_id=%s tenant_id=%s",
        claims.user_id,
        claims.tenant_id,
        extra={
            "event_type": "ws_connect",
            "auth_type": "ws_ticket",
            "user_id": claims.user_id,
            "tenant_id": claims.tenant_id,
        },
    )

    return WSAuthContext(
        auth_type="ws_ticket",
        user_id=claims.user_id,
        tenant_id=claims.tenant_id,
        role=claims.role,
        jti=claims.jti,
    )


def _extract_cookie_from_scope(scope: dict, name: str) -> str | None:
    """Extract cookie value from ASGI scope headers."""
    for key, value in scope.get("headers", []):
        if key.lower() == b"cookie":
            for part in value.decode("latin-1").split(";"):
                part = part.strip()
                if part.startswith(name + "="):
                    return part.split("=", 1)[1].strip().strip('"')
            break
    return None


async def resolve_ws_auth_from_cookie(cookie_token: str | None) -> WSAuthContext:
    """Validate JWT from HttpOnly cookie and return typed auth context.

    Raises WSAuthError with close code 4401 on failure.
    """
    if not cookie_token:
        logger.warning(
            "ws_auth.no_cookie",
            extra={"event_type": "auth_reject", "auth_type": "cookie"},
        )
        raise WSAuthError(close_code=4401)

    try:
        payload = jwt.decode(
            cookie_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        logger.warning(
            "ws_auth.invalid_cookie",
            extra={"event_type": "auth_reject", "auth_type": "cookie"},
        )
        raise WSAuthError(close_code=4401)

    username = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    role = payload.get("role", "user")

    if not username or tenant_id is None:
        logger.warning(
            "ws_auth.cookie_missing_claims",
            extra={"event_type": "auth_reject", "auth_type": "cookie"},
        )
        raise WSAuthError(close_code=4401)

    user_id: int
    async with async_session_local() as db:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            logger.warning(
                "ws_auth.cookie_user_invalid",
                extra={"event_type": "auth_reject", "auth_type": "cookie"},
            )
            raise WSAuthError(close_code=4401)
        if user.tenant_id != tenant_id:
            logger.warning(
                "ws_auth.cookie_tenant_mismatch",
                extra={"event_type": "auth_reject", "auth_type": "cookie"},
            )
            raise WSAuthError(close_code=4401)
        user_id = user.id

    logger.info(
        "ws_auth.ok user_id=%s tenant_id=%s",
        user_id,
        tenant_id,
        extra={
            "event_type": "ws_connect",
            "auth_type": "cookie",
            "user_id": user_id,
            "tenant_id": tenant_id,
        },
    )

    return WSAuthContext(
        auth_type="cookie",
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        jti=None,
    )
