import asyncio
from sqlalchemy import select
from app.db.session import async_session_local
from app.models.models import User

async def main():
    async with async_session_local() as db:
        r = await db.execute(select(User.id, User.username, User.is_active).where(User.username == "admin"))
        print(r.all())

if __name__ == "__main__":
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
