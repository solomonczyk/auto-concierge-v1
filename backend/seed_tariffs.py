import asyncio
from app.db.session import async_session_local
from app.models.models import TariffPlan, Tenant
from sqlalchemy import select

async def seed():
    async with async_session_local() as db:
        # 1. Seed Tariff Plans
        result = await db.execute(select(TariffPlan))
        if not result.scalars().all():
            db.add_all([
                TariffPlan(name='free', max_appointments=10, max_shops=1),
                TariffPlan(name='standard', max_appointments=100, max_shops=5),
                TariffPlan(name='pro', max_appointments=1000, max_shops=50)
            ])
            await db.commit()
            print('Tariff plans seeded.')
        else:
            print('Tariff plans already exist.')

if __name__ == "__main__":
    asyncio.run(seed())
