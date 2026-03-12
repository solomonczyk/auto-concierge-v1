"""Fix alembic version to match actual DB state."""
import asyncio
from sqlalchemy import text
from app.db.session import async_session_local


async def main():
    async with async_session_local() as db:
        # DB already has all tables from 2e13feb57458 + slug column
        # Set version to 2e13feb57458 (the current container head)
        await db.execute(text("UPDATE alembic_version SET version_num = '2e13feb57458'"))
        await db.commit()
        v = await db.execute(text("SELECT version_num FROM alembic_version"))
        print("alembic version now:", v.scalar())


asyncio.run(main())
