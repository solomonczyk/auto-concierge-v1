from datetime import datetime, timezone

from app.models.ws_auth_context import WSAuthContext
from app.services.ws_ticket_service import validate_ws_ticket, WSTicketValidationError, WSTicketClaims
from app.services.ws_ticket_store import consume_jti_once


class WSAuthError(Exception):
    """Raised when WS authentication fails."""
    def __init__(self, close_code: int):
        self.close_code = close_code


async def resolve_ws_auth(*, ticket: str | None) -> WSAuthContext:
    """Validate WS ticket and return typed auth context.

    Raises WSAuthError with appropriate WS close code on failure.
    """
    if not ticket:
        raise WSAuthError(close_code=4401)

    try:
        claims: WSTicketClaims = validate_ws_ticket(ticket=ticket)
    except WSTicketValidationError:
        raise WSAuthError(close_code=4401)

    now_ts = int(datetime.now(timezone.utc).timestamp())
    remaining_ttl = claims.exp - now_ts

    if not await consume_jti_once(jti=claims.jti, ttl_seconds=remaining_ttl):
        raise WSAuthError(close_code=4403)

    return WSAuthContext(
        user_id=claims.user_id,
        tenant_id=claims.tenant_id,
        role=claims.role,
        jti=claims.jti,
    )
