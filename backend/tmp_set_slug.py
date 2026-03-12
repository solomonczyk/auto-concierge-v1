"""Set proper slug for tenants."""
import asyncio
from sqlalchemy import text
from app.db.session import async_session_local


async def main():
    async with async_session_local() as db:
        # Fix tenant 3 slug (main production tenant)
        await db.execute(text("UPDATE tenants SET slug = 'auto-concierge' WHERE id = 3"))
        # Verify
        result = await db.execute(text("SELECT id, name, slug FROM tenants ORDER BY id"))
        for row in result.fetchall():
            print(row)
        await db.commit()
        print("Done!")


asyncio.run(main())
