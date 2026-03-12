import asyncio
from sqlalchemy import select
from app.db.session import async_session_local
from app.models.models import User
from app.core.security import verify_password

async def main():
    async with async_session_local() as db:
        r = await db.execute(select(User).where(User.username == "admin"))
        u = r.scalar_one()
        print("password_test_admin:", verify_password("admin", u.hashed_password))

if __name__ == "__main__":
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
