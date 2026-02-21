import asyncio
from app.db.session import async_session_local
from app.models.models import Tenant, TariffPlan
from app.core.security import get_token_hash, encrypt_token
from app.core.config import settings
from sqlalchemy import select

async def init_tenant():
    async with async_session_local() as db:
        token = settings.TELEGRAM_BOT_TOKEN
        token_hash = get_token_hash(token)
        
        # Get free tariff
        res = await db.execute(select(TariffPlan).where(TariffPlan.name == 'free'))
        tariff = res.scalar_one_or_none()
        
        # Check if exists
        res = await db.execute(select(Tenant).where(Tenant.bot_token_hash == token_hash))
        if not res.scalar_one_or_none():
            t = Tenant(
                name="Auto-Concierge Test Tenant",
                encrypted_bot_token=encrypt_token(token),
                bot_token_hash=token_hash,
                tariff_plan_id=tariff.id if tariff else None
            )
            db.add(t)
            await db.commit()
            print("First tenant initialized with encrypted token.")
        else:
            print("Tenant already exists.")

if __name__ == "__main__":
    asyncio.run(init_tenant())
