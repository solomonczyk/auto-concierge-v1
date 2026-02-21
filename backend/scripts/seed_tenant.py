import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_local
from app.models.models import Tenant, Shop, Service, User, UserRole, Tariff, TenantStatus
from app.core.security import get_password_hash
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_data():
    async with async_session_local() as db:
        # 1. Create Tenant
        tenant = Tenant(
            name="Auto-Concierge Demo",
            bot_token=settings.TELEGRAM_BOT_TOKEN,
            tariff=Tariff.PRO,
            status=TenantStatus.ACTIVE
        )
        db.add(tenant)
        await db.flush()
        logger.info(f"Created Tenant: {tenant.name} (ID: {tenant.id})")

        # 2. Create Shop
        shop = Shop(
            tenant_id=tenant.id,
            name="Demo Garage Central",
            address="ul. Pushkina, d. 10",
            phone="+7 (999) 000-00-01"
        )
        db.add(shop)
        await db.flush()
        logger.info(f"Created Shop: {shop.name} (ID: {shop.id})")

        # 3. Create Services
        services = [
            Service(tenant_id=tenant.id, name="Oil Change", duration_minutes=30, base_price=1500, description="Full oil and filter replacement"),
            Service(tenant_id=tenant.id, name="Brake Inspection", duration_minutes=45, base_price=800, description="Complete safety check of the braking system"),
            Service(tenant_id=tenant.id, name="Tire Rotation", duration_minutes=20, base_price=500, description="Rotate tires for even wear"),
            Service(tenant_id=tenant.id, name="General Diagnostics", duration_minutes=60, base_price=1200, description="Full vehicle scanning and visual check")
        ]
        db.add_all(services)
        logger.info(f"Added {len(services)} services")

        # 4. Create Admin User
        admin_user = User(
            tenant_id=tenant.id,
            shop_id=shop.id,
            username="admin@demo.ru",
            hashed_password=get_password_hash("admin123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        logger.info("Created Admin User: admin@demo.ru / admin123")

        await db.commit()
        logger.info("Seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
