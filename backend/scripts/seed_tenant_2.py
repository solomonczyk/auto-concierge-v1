import asyncio
import logging
from app.db.session import async_session_local
from app.models.models import Tenant, Shop, Service, User, UserRole, Tariff, TenantStatus
from app.core.security import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def seed_tenant_2():
    async with async_session_local() as db:
        # Create Tenant 2
        tenant = Tenant(
            name="Competitor Service",
            bot_token="SECOND_BOT_TOKEN",
            tariff=Tariff.FREE,
            status=TenantStatus.ACTIVE
        )
        db.add(tenant)
        await db.flush()

        # Create Shop 2
        shop = Shop(
            tenant_id=tenant.id,
            name="Rival Autoshop",
            address="Other Street, 5",
            phone="+7 (999) 000-00-66"
        )
        db.add(shop)
        await db.flush()

        # Create Service 2 (Unique to Tenant 2)
        service = Service(
            tenant_id=tenant.id, 
            name="Secret Tuning", 
            duration_minutes=120, 
            base_price=50000, 
            description="Highly classified performance upgrade"
        )
        db.add(service)

        # Create Admin User 2
        admin_user = User(
            tenant_id=tenant.id,
            shop_id=shop.id,
            username="rival@autoshop.ru",
            hashed_password=get_password_hash("password123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)

        await db.commit()
        logger.info("Tenant 2 seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_tenant_2())
