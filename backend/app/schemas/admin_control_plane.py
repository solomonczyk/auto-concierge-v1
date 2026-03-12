"""
Admin Control Plane — unified response contracts.
Single source of truth for /admin/control-plane and /admin/tenants endpoints.
Naming: telegram_bot_registered, telegram_webhook_active, shop_configured, services_configured.
"""
from datetime import datetime
from pydantic import BaseModel


# --- Platform summary ---
class ControlPlaneSummaryResponse(BaseModel):
    total_tenants: int
    active_tenants: int
    pending_tenants: int
    suspended_tenants: int
    ready_tenants: int
    not_ready_tenants: int
    tenants_without_shop: int
    tenants_without_services: int
    tenants_without_bot: int
    tenants_without_webhook: int


# --- Tenants overview (list item) ---
class TenantOverviewItem(BaseModel):
    tenant_id: int
    name: str
    slug: str | None
    status: str
    shop_configured: bool
    services_configured: bool
    telegram_bot_registered: bool
    telegram_webhook_active: bool
    booking_ready: bool


# --- Tenant detail ---
class TenantOnboardingState(BaseModel):
    tenant_created: bool
    tariff_assigned: bool
    telegram_bot_registered: bool
    webhook_provisioned: bool
    readiness_ok: bool
    onboarding_complete: bool
    missing_steps: list[str] = []


class TenantReadinessFlags(BaseModel):
    shop_configured: bool
    services_configured: bool
    telegram_bot_registered: bool
    telegram_webhook_active: bool
    booking_ready: bool
    tenant_status: str
    tenant_operational: bool


class ShopInfo(BaseModel):
    id: int
    name: str
    address: str | None


class TelegramBotInfo(BaseModel):
    id: int
    bot_username: str | None
    is_active: bool
    webhook_status: str
    webhook_last_error: str | None
    webhook_last_synced_at: str | None


class TenantDetailResponse(BaseModel):
    tenant_id: int
    name: str
    slug: str | None
    status: str
    onboarding_state: TenantOnboardingState
    readiness: TenantReadinessFlags
    shop: ShopInfo | None
    services_count: int
    telegram_bot: TelegramBotInfo | None
    created_at: str | None


# --- Actions response ---
class ActivateBotResponse(BaseModel):
    tenant_id: int
    action: str = "activate_bot"
    success: bool = True
    message: str = "Telegram bot is ready for activation"


class ProvisionWebhookResponse(BaseModel):
    tenant_id: int
    action: str = "provision_webhook"
    success: bool
    status: str
    message: str
    error: str | None = None


class FinalizeOnboardingResponse(BaseModel):
    tenant_id: int
    action: str = "finalize_onboarding"
    finalized: bool = True
    message: str
