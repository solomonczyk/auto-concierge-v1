"""
Plan limits config — SaaS-ready limits per plan (starter, business, enterprise).
Limits are in config/service layer; no DB table required.
"""
from typing import TypedDict

# Plan names (must match tariff_plans.name)
PLAN_STARTER = "starter"
PLAN_BUSINESS = "business"
PLAN_ENTERPRISE = "enterprise"

# Legacy mapping for backward compat
PLAN_ALIAS = {
    "free": PLAN_STARTER,
    "standard": PLAN_BUSINESS,
    "pro": PLAN_ENTERPRISE,
}


class PlanLimitsConfig(TypedDict):
    max_users: int
    max_appointments_per_month: int
    max_webhook_requests_per_day: int
    max_ai_requests_per_day: int


PLAN_LIMITS: dict[str, PlanLimitsConfig] = {
    PLAN_STARTER: {
        "max_users": 3,
        "max_appointments_per_month": 50,
        "max_webhook_requests_per_day": 100,
        "max_ai_requests_per_day": 0,  # no AI on starter
    },
    PLAN_BUSINESS: {
        "max_users": 15,
        "max_appointments_per_month": 500,
        "max_webhook_requests_per_day": 2000,
        "max_ai_requests_per_day": 100,
    },
    PLAN_ENTERPRISE: {
        "max_users": 100,
        "max_appointments_per_month": 5000,
        "max_webhook_requests_per_day": 20000,
        "max_ai_requests_per_day": 1000,
    },
}


def normalize_plan_name(name: str | None) -> str:
    """Map plan name to canonical starter/business/enterprise."""
    if not name:
        return PLAN_STARTER
    return PLAN_ALIAS.get(name.lower(), name.lower())


def get_limits(plan_name: str | None) -> PlanLimitsConfig:
    """Return limits for the given plan. Defaults to starter."""
    canonical = normalize_plan_name(plan_name)
    return PLAN_LIMITS.get(canonical, PLAN_LIMITS[PLAN_STARTER])
