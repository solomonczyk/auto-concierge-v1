from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from jose import JWTError, jwt

from app.core.config import settings
from app.models.ws_auth_context import WSAuthContext

WS_TICKET_TTL_SECONDS = 45
WS_TICKET_TYPE = "ws_ticket"


class WSTicketValidationError(ValueError):
    pass


def _get_ws_signing_key() -> str:
    return settings.SECRET_KEY


def create_ws_ticket(
    *,
    user_id: int,
    tenant_id: int,
    role: str,
    ttl_seconds: int = WS_TICKET_TTL_SECONDS,
) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    claims: dict[str, Any] = {
        "type": WS_TICKET_TYPE,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
    return jwt.encode(claims, _get_ws_signing_key(), algorithm=settings.ALGORITHM)


class WSTicketClaims(WSAuthContext):
    """Extends WSAuthContext with ticket-specific fields needed for anti-replay."""
    exp: int
    model_config = {"frozen": True}


def validate_ws_ticket(*, ticket: str) -> WSTicketClaims:
    if not ticket:
        raise WSTicketValidationError("Missing ws ticket")

    try:
        raw_claims = jwt.decode(ticket, _get_ws_signing_key(), algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise WSTicketValidationError("Invalid ws ticket") from exc

    required_claims = ("type", "user_id", "tenant_id", "role", "exp", "jti")
    missing = [name for name in required_claims if name not in raw_claims]
    if missing:
        raise WSTicketValidationError(f"Missing claims: {', '.join(missing)}")

    if raw_claims.get("type") != WS_TICKET_TYPE:
        raise WSTicketValidationError("Invalid ws ticket type")

    return WSTicketClaims(
        user_id=raw_claims["user_id"],
        tenant_id=raw_claims["tenant_id"],
        role=raw_claims["role"],
        jti=raw_claims["jti"],
        exp=raw_claims["exp"],
    )
