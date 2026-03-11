"""Tenant lifecycle schemas — status read/update and response contracts."""
from pydantic import BaseModel

from app.models.models import TenantStatus


class TenantStatusRead(BaseModel):
    """Read schema for tenant status."""

    tenant_id: int
    status: str

    class Config:
        from_attributes = True


class TenantStatusUpdate(BaseModel):
    """Update/request schema for tenant status change."""

    status: TenantStatus


class TenantLifecycleResponse(BaseModel):
    """Lifecycle summary for admin / SaaS control plane."""

    tenant_id: int
    status: str
    operational: bool
    billing_ok: bool
    readiness_ok: bool
