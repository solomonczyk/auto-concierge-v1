import asyncio, sys
sys.path.insert(0, '/app')

async def go():
    from app.db.session import async_session_local
    from app.models.models import Tenant
    from sqlalchemy import select
    async with async_session_local() as db:
        r = await db.execute(select(Tenant))
        for t in r.scalars().all():
            print('id=' + str(t.id) + ' slug=' + str(t.slug) + ' name=' + t.name)

asyncio.run(go())
