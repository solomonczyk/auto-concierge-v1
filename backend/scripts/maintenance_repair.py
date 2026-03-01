
import asyncio
import logging
from sqlalchemy import select, text, delete
from app.db.session import async_session_local
from app.models.models import Tenant, Service, Shop, Client
from app.bot.tenant import get_or_create_tenant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_maintenance():
    async with async_session_local() as db:
        # 1. Identify active bot tenant
        tenant = await get_or_create_tenant(db)
        logger.info(f"Active Bot Tenant: ID={tenant.id}, Name={tenant.name}")

        # 2. Get Shop for this tenant
        shop_stmt = select(Shop).where(Shop.tenant_id == tenant.id)
        result = await db.execute(shop_stmt)
        shop = result.scalar_one_or_none()
        
        if not shop:
            logger.info("Creating default shop for tenant...")
            shop = Shop(tenant_id=tenant.id, name="AutoService Main", address="г. Москва", phone="777")
            db.add(shop)
            await db.flush()

        # 3. TRUNCATE services to reset IDs (Sequential numbering #1, #2...)
        # Note: We use execute(text(...)) because delete() doesn't reset auto-increment
        logger.info("Resetting services table...")
        await db.execute(text("TRUNCATE TABLE services RESTART IDENTITY CASCADE;"))
        await db.commit()

        # 4. Define services to seed
        services_to_seed = [
            {"name": "Замена масла и фильтра", "price": 1500, "duration": 45},
            {"name": "Шиномонтаж", "price": 2000, "duration": 60},
            {"name": "Диагностика ходовой", "price": 800, "duration": 30},
            {"name": "Замена тормозных колодок", "price": 2500, "duration": 90},
            {"name": "Компьютерная диагностика", "price": 1200, "duration": 40},
            {"name": "Замена свечей зажигания", "price": 1000, "duration": 30},
            {"name": "Заправка кондиционера", "price": 2500, "duration": 60},
            {"name": "Мойка двигателя", "price": 1000, "duration": 45},
            {"name": "Диагностика электрооборудования", "price": 500, "duration": 30},
            {"name": "Развал-схождение", "price": 1500, "duration": 40},
        ]

        logger.info(f"Seeding {len(services_to_seed)} services for tenant {tenant.id}...")
        for s_data in services_to_seed:
            service = Service(
                tenant_id=tenant.id,
                name=s_data["name"],
                base_price=s_data["price"],
                duration_minutes=s_data["duration"]
            )
            db.add(service)

        await db.commit()
        logger.info("Maintenance completed successfully.")

if __name__ == "__main__":
    asyncio.run(run_maintenance())
