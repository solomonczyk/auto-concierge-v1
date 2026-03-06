"""
Create demo tenant for sales demonstrations.
Dashboard: https://bt-aistudio.ru/concierge/demo-service
WebApp:    https://bt-aistudio.ru/concierge/demo-service/webapp

Usage:
  docker exec -it autoservice_api_prod python scripts/create_demo_tenant.py

  Or locally (with .env):
  cd backend && PYTHONPATH=. python scripts/create_demo_tenant.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import async_session_local
from app.models.models import (
    Tenant,
    TenantStatus,
    TenantSettings,
    Shop,
    Service,
    User,
    UserRole,
    TariffPlan,
)
from app.core.security import get_password_hash

DEMO_NAME = "Demo Auto Service"
DEMO_SLUG = "demo-service"
DEMO_ADMIN_USER = "demo_admin"
DEMO_ADMIN_PASS = "demo12345"

DEFAULT_SERVICES = [
    {"name": "Замена масла и фильтра", "base_price": 800.0, "duration_minutes": 30},
    {"name": "Диагностика двигателя", "base_price": 500.0, "duration_minutes": 60},
    {"name": "Замена тормозных колодок", "base_price": 1200.0, "duration_minutes": 60},
    {"name": "Шиномонтаж (4 колеса)", "base_price": 1600.0, "duration_minutes": 60},
]


async def create_demo_tenant() -> None:
    async with async_session_local() as db:
        existing = await db.execute(select(Tenant).where(Tenant.slug == DEMO_SLUG))
        if existing.scalar_one_or_none():
            print(f"[OK] Tenant '{DEMO_SLUG}' already exists.")
            print(f"     Dashboard: https://bt-aistudio.ru/concierge/{DEMO_SLUG}")
            return

        username_check = await db.execute(select(User).where(User.username == DEMO_ADMIN_USER))
        if username_check.scalar_one_or_none():
            print(f"[ERROR] Username '{DEMO_ADMIN_USER}' already taken. Choose another.")
            sys.exit(1)

        # Tariff
        tariff_res = await db.execute(select(TariffPlan).where(TariffPlan.name == "free"))
        tariff = tariff_res.scalar_one_or_none()

        # 1. Tenant
        tenant = Tenant(
            name=DEMO_NAME,
            slug=DEMO_SLUG,
            status=TenantStatus.ACTIVE,
            tariff_plan_id=tariff.id if tariff else None,
        )
        db.add(tenant)
        await db.flush()

        # 2. Shop (required for slots/booking)
        shop = Shop(
            tenant_id=tenant.id,
            name="Главный цех",
            address="Демо-адрес",
        )
        db.add(shop)
        await db.flush()

        # 3. TenantSettings
        settings = TenantSettings(
            tenant_id=tenant.id,
            work_start=9,
            work_end=18,
            slot_duration=30,
            timezone="Europe/Moscow",
        )
        db.add(settings)

        # 4. Admin user
        admin = User(
            tenant_id=tenant.id,
            username=DEMO_ADMIN_USER,
            hashed_password=get_password_hash(DEMO_ADMIN_PASS),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)

        # 5. Services
        for item in DEFAULT_SERVICES:
            svc = Service(
                tenant_id=tenant.id,
                name=item["name"],
                base_price=item["base_price"],
                duration_minutes=item["duration_minutes"],
            )
            db.add(svc)

        await db.commit()

    print("[OK] Demo tenant created.")
    print(f"     Slug:     {DEMO_SLUG}")
    print(f"     Admin:    {DEMO_ADMIN_USER} / {DEMO_ADMIN_PASS}")
    print(f"     Dashboard: https://bt-aistudio.ru/concierge/{DEMO_SLUG}")
    print(f"     WebApp:   https://bt-aistudio.ru/concierge/{DEMO_SLUG}/webapp")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(create_demo_tenant())
