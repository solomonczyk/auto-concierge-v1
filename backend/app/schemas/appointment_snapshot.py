"""
Appointment snapshot read-model schemas.

Canonical contract for reading appointment data.
Source of truth for: operator UI, reminders, client WebApp, reschedule/cancel, support.

CONTRACT FROZEN: New consumers must use snapshot instead of assembling
their own read model from multiple endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AppointmentSnapshotClient(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None


class AppointmentSnapshotService(BaseModel):
    id: int
    name: str


class AppointmentSnapshotShop(BaseModel):
    id: int
    name: str


class AppointmentSnapshotIntake(BaseModel):
    status: str


class AppointmentSnapshotResponse(BaseModel):
    appointment_id: int
    tenant_id: int
    status: str
    start_time: datetime
    end_time: datetime
    client: Optional[AppointmentSnapshotClient] = None
    service: Optional[AppointmentSnapshotService] = None
    shop: Optional[AppointmentSnapshotShop] = None
    intake: Optional[AppointmentSnapshotIntake] = None
    source: str
    is_waitlist: bool


class AppointmentCancelResponse(BaseModel):
    """Response for POST /appointments/{id}/cancel. Returns snapshot with cancelled flag."""
    appointment_id: int
    tenant_id: int
    status: str
    cancelled: bool
    snapshot: AppointmentSnapshotResponse


class AppointmentRescheduleRequest(BaseModel):
    """Request for POST /appointments/{id}/reschedule."""
    new_start_time: datetime
    new_end_time: datetime
    reason: Optional[str] = None


class AppointmentRescheduleResponse(BaseModel):
    """Response for POST /appointments/{id}/reschedule. Returns old/new times and updated snapshot."""
    appointment_id: int
    tenant_id: int
    rescheduled: bool
    old_start_time: datetime
    old_end_time: datetime
    new_start_time: datetime
    new_end_time: datetime
    status: str
    snapshot: AppointmentSnapshotResponse
