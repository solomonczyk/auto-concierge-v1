import asyncio
from sqlalchemy import select
from app.db.session import async_session_local
from app.models.models import Service

async def main():
    async with async_session_local() as db:
        r = await db.execute(select(Service).where(Service.tenant_id == 3))
        svcs = r.scalars().all()
        print("Services count:", len(svcs))
        for s in svcs[:5]:
            print(s.id, s.name)

if __name__ == "__main__":
    asyncio.run(main())
