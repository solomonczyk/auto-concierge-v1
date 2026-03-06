import asyncio, sys
sys.path.insert(0, '/app')

async def go():
    from app.db.session import async_session_local
    from app.models.models import User, UserRole
    from sqlalchemy import select
    async with async_session_local() as db:
        r = await db.execute(select(User))
        for u in r.scalars().all():
            print(u.username, str(u.role), 'tenant_id=' + str(u.tenant_id))

asyncio.run(go())
