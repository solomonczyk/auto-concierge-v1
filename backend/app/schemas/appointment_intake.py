from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AppointmentIntakeRead(BaseModel):
    status: str
    answers_json: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
