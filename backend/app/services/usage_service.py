"""
Usage counters and limit enforcement for SaaS billing.
"""
from datetime import datetime, timezone as tz

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Appointment, User
from app.services.plan_limits import get_limits, normalize_plan_name


class LimitExceededError(Exception):
    """Raised when tenant exceeds a plan limit."""

    def __init__(self, limit_name: str, current: int, limit: int):
        self.limit_name = limit_name
        self.current = current
        self.limit = limit
        super().__init__(f"Limit exceeded: {limit_name} (current={current}, limit={limit})")

    def to_detail(self) -> dict:
        return {
            "code": "limit_exceeded",
            "limit_name": self.limit_name,
            "current": self.current,
            "limit": self.limit,
            "message": f"Limit exceeded: {self.limit_name} (current={self.current}, limit={self.limit})",
        }


async def get_appointments_this_month(db: AsyncSession, tenant_id: int) -> int:
    """Count appointments created this month (UTC) for tenant."""
    now = datetime.now(tz.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(Appointment.id)).where(
        and_(
            Appointment.tenant_id == tenant_id,
            Appointment.created_at >= month_start,
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def get_users_count(db: AsyncSession, tenant_id: int) -> int:
    """Count users for tenant (excluding SUPERADMIN without tenant)."""
    from app.models.models import UserRole

    stmt = select(func.count(User.id)).where(
        and_(User.tenant_id == tenant_id, User.role != UserRole.SUPERADMIN)
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def check_appointments_limit(
    db: AsyncSession,
    tenant_id: int,
    plan_name: str | None,
) -> None:
    """
    Check if tenant can create one more appointment this month.
    Raises LimitExceededError if limit exceeded.
    """
    limits = get_limits(plan_name)
    current = await get_appointments_this_month(db, tenant_id)
    limit_val = limits["max_appointments_per_month"]
    if current >= limit_val:
        raise LimitExceededError(
            limit_name="max_appointments_per_month",
            current=current,
            limit=limit_val,
        )


def can_use_feature(plan_name: str | None, feature: str) -> bool:
    """
    Plan-aware feature gating.
    Features: webhook (business+), ai (business+), advanced_analytics (enterprise only).
    """
    canonical = normalize_plan_name(plan_name)
    if feature == "webhook":
        return canonical in ("business", "enterprise")
    if feature == "ai":
        return canonical in ("business", "enterprise")
    if feature == "advanced_analytics":
        return canonical == "enterprise"
    return False


def get_features_for_plan(plan_name: str | None) -> dict[str, bool]:
    """Return feature flags for the given plan."""
    return {
        "webhook": can_use_feature(plan_name, "webhook"),
        "ai": can_use_feature(plan_name, "ai"),
        "advanced_analytics": can_use_feature(plan_name, "advanced_analytics"),
    }
