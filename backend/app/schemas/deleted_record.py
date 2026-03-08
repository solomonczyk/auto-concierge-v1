from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DeletedAppointmentRead(BaseModel):
    id: int
    tenant_id: int
    shop_id: int
    client_id: int
    service_id: int
    status: str
    start_time: datetime
    end_time: datetime
    deleted_at: datetime
    deleted_by: Optional[int] = None

    class Config:
        from_attributes = True


class DeletedAppointmentListResponse(BaseModel):
    items: list[DeletedAppointmentRead]
    total: int
    limit: int
    offset: int


class DeletedClientRead(BaseModel):
    id: int
    tenant_id: int
    full_name: str
    phone: Optional[str] = None
    telegram_id: Optional[int] = None
    car_make: Optional[str] = None
    car_year: Optional[int] = None
    vin: Optional[str] = None
    deleted_at: datetime
    deleted_by: Optional[int] = None

    class Config:
        from_attributes = True


class DeletedClientListResponse(BaseModel):
    items: list[DeletedClientRead]
    total: int
    limit: int
    offset: int
