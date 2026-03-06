import asyncio
import sys
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from urllib.parse import quote_plus

# Add parent dir to path to import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.db.session import engine, async_session_local
from app.models.models import TariffPlan, Tenant, Shop, Client, Service
from app.core.security import get_token_hash, encrypt_token

async def create_db_if_not_exists():
    # Connect to 'postgres' to create 'autoservice'
    admin_uri = f"postgresql+asyncpg://{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}@{settings.POSTGRES_SERVER}/postgres"
    admin_engine = create_async_engine(admin_uri, isolation_level="AUTOCOMMIT")
    async with admin_engine.connect() as conn:
        result = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{settings.POSTGRES_DB}'"))
        if not result.scalar():
            await conn.execute(text(f"CREATE DATABASE {settings.POSTGRES_DB}"))
            print(f"Database {settings.POSTGRES_DB} created.")
        else:
            print(f"Database {settings.POSTGRES_DB} already exists.")
    await admin_engine.dispose()

async def init_data():
    async with async_session_local() as db:
        # 1. Seed Tariffs
        res = await db.execute(text("SELECT COUNT(*) FROM tariff_plans"))
        if res.scalar() == 0:
            free_tariff = TariffPlan(name="free", max_appointments=300, max_shops=1)
            db.add(free_tariff)
            await db.flush()
            print("Tariff plans seeded.")
        
        # 2. Seed Tenant (Bot)
        token = settings.TELEGRAM_BOT_TOKEN
        token_hash = get_token_hash(token)
        res = await db.execute(text(f"SELECT id FROM tenants WHERE bot_token_hash = '{token_hash}'"))
        tenant = res.scalar_one_or_none()
        if not tenant:
            res = await db.execute(text("SELECT id FROM tariff_plans WHERE name = 'free'"))
            tariff_id = res.scalar()
            
            tenant = Tenant(
                name="Auto-Concierge Production Tenant",
                encrypted_bot_token=encrypt_token(token),
                bot_token_hash=token_hash,
                tariff_plan_id=tariff_id
            )
            db.add(tenant)
            await db.flush()
            print("Tenant seeded.")
        
        # 3. Seed Shop
        res = await db.execute(text(f"SELECT id FROM shops WHERE tenant_id = {tenant.id}"))
        if not res.scalar_one_or_none():
            shop = Shop(
                tenant_id=tenant.id,
                name="Main Workshop",
                address="Remote",
            )
            db.add(shop)
            await db.flush()
            print("Shop seeded.")
            
        await db.commit()
        print("Initialization complete.")

async def main():
    await create_db_if_not_exists()
    # Migrations should be run via alembic separately, but let's assume 'head' for now
    # In a real script we might call alembic programmatically
    print("Please run 'alembic upgrade head' before running data init if DB was just created.")
    await init_data()

if __name__ == "__main__":
    asyncio.run(main())
