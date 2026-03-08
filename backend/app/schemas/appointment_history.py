from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AppointmentHistoryRead(BaseModel):
    """Read model for appointment status change audit log."""

    id: int
    appointment_id: int
    old_status: str
    new_status: str
    reason: Optional[str] = None
    created_at: datetime
    actor: Optional[str] = None

    class Config:
        from_attributes = True
