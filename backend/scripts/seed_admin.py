"""
Seed script to create initial tenant, shop, and admin user.
Run: docker exec -e PYTHONPATH=/app autoservice_api_prod python scripts/seed_admin.py
"""
import asyncio
import sys
import os
sys.path.insert(0, '/app')

from app.db.session import async_session_local
from app.models.models import Tenant, Shop, User, UserRole, TenantStatus
from app.core.security import get_password_hash


async def seed():
    async with async_session_local() as db:
        # 1. Create Tenant
        tenant = Tenant(
            name="Auto-Concierge Demo",
            status=TenantStatus.ACTIVE
        )
        db.add(tenant)
        await db.flush()
        print(f"Tenant created: id={tenant.id}, name={tenant.name}")

        # 2. Create Shop
        shop = Shop(
            tenant_id=tenant.id,
            name="Demo Garage",
            address="ul. Pushkina 10",
            phone="+7 999 000 0001"
        )
        db.add(shop)
        await db.flush()
        print(f"Shop created: id={shop.id}, name={shop.name}")

        # 3. Create Admin User
        user = User(
            tenant_id=tenant.id,
            shop_id=shop.id,
            username="admin",
            hashed_password=get_password_hash("admin123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(user)
        await db.commit()
        print("Admin user created: login=admin  password=admin123")
        print("Seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
