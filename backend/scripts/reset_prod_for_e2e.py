"""
Reset prod DB state for reliable E2E:
- Clears appointments for slug=auto-concierge (frees all slots)
- Ensures shop + at least one service exist
Run: docker exec -i autoservice_api_prod python3 /app/scripts/reset_prod_for_e2e.py
"""
import asyncio
import sys
sys.path.insert(0, '/app')

async def main():
    from app.db.session import async_session_local
    from app.models.models import Tenant, Shop, Service, Appointment
    from sqlalchemy import select, delete

    async with async_session_local() as db:
        tenant = (await db.execute(select(Tenant).where(Tenant.slug == 'auto-concierge'))).scalar_one_or_none()
        if not tenant:
            print('Tenant auto-concierge not found')
            return
        tid = tenant.id
        shop = (await db.execute(select(Shop).where(Shop.tenant_id == tid))).scalar_one_or_none()
        if not shop:
            shop = Shop(tenant_id=tid, name='Main Workshop', address='Remote')
            db.add(shop)
            await db.flush()
            print('Created shop')
        service = (await db.execute(select(Service).where(Service.tenant_id == tid).limit(1))).scalar_one_or_none()
        if not service:
            service = Service(tenant_id=tid, shop_id=shop.id, name='Диагностика', duration_minutes=30, base_price=1000)
            db.add(service)
            await db.flush()
            print('Created default service')
        result = await db.execute(delete(Appointment).where(Appointment.tenant_id == tid))
        await db.commit()
        print(f'Deleted {result.rowcount} appointments for tenant {tid}. Slots freed.')

if __name__ == '__main__':
    asyncio.run(main())
