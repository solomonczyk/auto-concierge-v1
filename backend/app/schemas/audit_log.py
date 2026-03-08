from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: int
    tenant_id: Optional[int] = None
    actor_user_id: Optional[int] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    payload_before: Optional[dict[str, Any]] = None
    payload_after: Optional[dict[str, Any]] = None
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: list[AuditLogRead]
    total: int
    limit: int
    offset: int
