import asyncio
import os
import sys
import logging

# Add project root to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), "backend", ".env"))

from sqlalchemy import select
from app.db.session import async_session_local
from app.models.models import Tenant, User, Shop, Service, UserRole
from app.core.security import get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env-driven seed contract (CI/E2E alignment)
SEED_TENANT_NAME = os.getenv("SEED_TENANT_NAME", "Default Tenant")
SEED_TENANT_SLUG = os.getenv("SEED_TENANT_SLUG", "auto-concierge")
SEED_SHOP_NAME = os.getenv("SEED_SHOP_NAME", "Best Auto")
SEED_ADMIN_USER = os.getenv("SEED_ADMIN_USER", "admin")
SEED_ADMIN_PASS = os.getenv("SEED_ADMIN_PASS", "admin")

POPULAR_SERVICES = [
    {"name": "Замена масла и фильтра", "duration": 45, "price": 1500.0},
    {"name": "Диагностика ходовой", "duration": 30, "price": 1000.0},
    {"name": "Замена тормозных колодок", "duration": 60, "price": 2500.0},
    {"name": "Компьютерная диагностика", "duration": 30, "price": 1200.0},
    {"name": "Шиномонтаж (комплекс)", "duration": 60, "price": 3000.0},
    {"name": "Развал-схождение", "duration": 45, "price": 2000.0},
    {"name": "Замена свечей зажигания", "duration": 45, "price": 1500.0},
    {"name": "Заправка кондиционера", "duration": 40, "price": 2500.0},
    {"name": "Замена ремня ГРМ", "duration": 180, "price": 8000.0},
    {"name": "Промывка инжектора", "duration": 60, "price": 3500.0},
]

async def seed_data():
    async with async_session_local() as db:
        try:
            # 0. Check/Create Tenant
            logger.info("Checking Tenant...")
            result = await db.execute(select(Tenant).where(Tenant.name == SEED_TENANT_NAME))
            tenant = result.scalar_one_or_none()

            if not tenant:
                tenant = Tenant(name=SEED_TENANT_NAME, slug=SEED_TENANT_SLUG)
                db.add(tenant)
                await db.flush()
                logger.info("Created Tenant")
            else:
                logger.info("Tenant already exists")

            # 1. Check/Create Shop
            logger.info("Checking Shop...")
            result = await db.execute(select(Shop).where(Shop.name == SEED_SHOP_NAME))
            shop = result.scalar_one_or_none()
            
            if not shop:
                shop = Shop(
                    tenant_id=tenant.id,
                    name=SEED_SHOP_NAME,
                    address="123 Main St"
                )
                db.add(shop)
                await db.flush()
                logger.info(f"Created Shop: {shop.name}")
            else:
                logger.info(f"Shop already exists: {shop.name}")

            # 2. Check/Create Admin User
            logger.info("Checking Admin User...")
            result = await db.execute(select(User).where(User.username == SEED_ADMIN_USER))
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    tenant_id=tenant.id,
                    username=SEED_ADMIN_USER,
                    hashed_password=get_password_hash(SEED_ADMIN_PASS),
                    shop_id=shop.id,
                    role=UserRole.ADMIN
                )
                db.add(user)
                await db.flush()
                logger.info("Created Admin User")
            else:
                logger.info("Admin User already exists")

            # 3. Check/Create Services
            logger.info("Checking Services...")
            result = await db.execute(select(Service))
            existing_services = result.scalars().all()
            existing_names = {s.name for s in existing_services}
            
            new_services = []
            for svc in POPULAR_SERVICES:
                if svc["name"] not in existing_names:
                    new_service = Service(
                        tenant_id=tenant.id,
                        name=svc["name"],
                        duration_minutes=svc["duration"],
                        base_price=svc["price"]
                    )
                    new_services.append(new_service)
            
            if new_services:
                db.add_all(new_services)
                logger.info(f"Adding {len(new_services)} new services...")
            else:
                logger.info("All popular services already exist.")

            await db.commit()
            logger.info("Seeding completed successfully!")

        except Exception as e:
            logger.error(f"Error during seeding: {e}")
            await db.rollback()
            raise

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed_data())
