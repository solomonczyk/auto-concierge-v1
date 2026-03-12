"""
SaaS Provisioning / Onboarding — request and response contracts.

Tenant creation: minimal required fields; initial status is lifecycle-managed (PENDING).
"""
from pydantic import BaseModel, field_validator


class TenantCreateRequest(BaseModel):
    """Request schema for creating a tenant (SaaS onboarding entry point)."""

    name: str
    slug: str
    contact_email: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("name must not be empty")
        return v[:100]

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("slug must be 3–50 characters")
        if not v.replace("-", "").isalnum():
            raise ValueError("slug must be lowercase letters, digits and hyphens only")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("slug must not start or end with a hyphen")
        return v


class TenantCreateResponse(BaseModel):
    """Response schema for tenant creation — minimal contract."""

    id: int
    name: str
    slug: str
    status: str

    class Config:
        from_attributes = True


class TenantTariffAssignRequest(BaseModel):
    """Request schema for assigning tariff to tenant."""

    tariff_plan_id: int | None = None
    tariff_code: str | None = None  # e.g. starter, business, enterprise


class TenantTariffAssignResponse(BaseModel):
    """Response after tariff assignment."""

    tenant_id: int
    tariff_plan_id: int
    tariff_code: str


class TenantOnboardingStateResponse(BaseModel):
    """GET /tenants/{id}/onboarding — onboarding progress and completion."""

    tenant_id: int
    tenant_created: bool
    tariff_assigned: bool
    telegram_bot_registered: bool
    webhook_provisioned: bool
    readiness_ok: bool
    onboarding_complete: bool
    missing_steps: list[str] = []
