"""Fix admin user tenant_id to match PUBLIC_TENANT_ID (3)."""
import asyncio
from sqlalchemy import text
from app.db.session import async_session_local

async def main():
    async with async_session_local() as db:
        await db.execute(text("UPDATE users SET tenant_id = 3 WHERE username = 'admin'"))
        await db.commit()
        print("OK: admin tenant_id set to 3")

if __name__ == "__main__":
    asyncio.run(main())
