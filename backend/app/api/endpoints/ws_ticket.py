from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api import deps
from app.models.models import User
from app.services.ws_ticket_service import WS_TICKET_TTL_SECONDS, create_ws_ticket

router = APIRouter()


class WSTicketResponse(BaseModel):
    ticket: str
    expires_in: int
    token_type: str


@router.post("/ws-ticket", response_model=WSTicketResponse)
async def issue_ws_ticket(
    current_user: User = Depends(deps.get_current_active_user),
) -> WSTicketResponse:
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context required for ws ticket",
        )

    ticket = create_ws_ticket(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        role=current_user.role.value,
    )
    return WSTicketResponse(
        ticket=ticket,
        expires_in=WS_TICKET_TTL_SECONDS,
        token_type="ws_ticket",
    )
