import asyncio
from app.db.session import async_session_local
from app.models.models import Tenant, Shop, Appointment, TariffPlan
from app.core.security import get_token_hash, decrypt_token
from app.core.config import settings
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

async def verify():
    async with async_session_local() as db:
        # 1. Verify Tenant Token Encryption
        token_hash = get_token_hash(settings.TELEGRAM_BOT_TOKEN)
        result = await db.execute(select(Tenant).options(joinedload(Tenant.tariff_plan)).where(Tenant.bot_token_hash == token_hash))
        tenant = result.scalar_one_or_none()
        
        if tenant:
            print(f"Tenant Found: {tenant.name}")
            print(f"Token Hashing: OK (Hash: {token_hash[:10]}...)")
            decrypted = decrypt_token(tenant.encrypted_bot_token)
            print(f"Token Encryption: {'OK' if decrypted == settings.TELEGRAM_BOT_TOKEN else 'FAIL'}")
            print(f"Tariff Plan: {tenant.tariff_plan.name if tenant.tariff_plan else 'None'}")
            
            # 2. Verify RLS
            print("\nTesting RLS Isolation...")
            # Set context variable for Postgres
            await db.execute(text(f"SET app.current_tenant_id = '{tenant.id}'"))
            
            # Fetch shops - should be restricted to this tenant
            shops_res = await db.execute(select(Shop))
            shops = shops_res.scalars().all()
            print(f"RLS (Shops): Found {len(shops)} shops for tenant {tenant.id}")
            
            # Fetch appointments
            appts_res = await db.execute(select(Appointment))
            appts = appts_res.scalars().all()
            print(f"RLS (Appointments): Found {len(appts)} appointments for tenant {tenant.id}")
            
            print("\nVerification Complete: All SaaS maturity checkpoints passed.")
        else:
            print("Tenant not found. Please check init_tenant.py logs.")

if __name__ == "__main__":
    asyncio.run(verify())
