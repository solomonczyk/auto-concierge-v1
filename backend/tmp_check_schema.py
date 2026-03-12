"""Check tenants table schema and fix alembic version."""
import asyncio
from sqlalchemy import text
from app.db.session import async_session_local


async def main():
    async with async_session_local() as db:
        # Check columns in tenants table
        result = await db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='tenants' ORDER BY ordinal_position"
        ))
        cols = [r[0] for r in result.fetchall()]
        print("tenants columns:", cols)

        # Check alembic version
        v = await db.execute(text("SELECT version_num FROM alembic_version"))
        print("alembic version:", v.scalar())

        # If slug exists, reset alembic to f0a4addd46ec so we can generate
        # a clean migration from the current container
        if 'slug' in cols:
            print("slug column EXISTS - resetting alembic version to f0a4addd46ec")
            await db.execute(text("UPDATE alembic_version SET version_num = 'f0a4addd46ec'"))
            await db.commit()
            print("Done - alembic version reset")
        else:
            print("slug column MISSING - need to apply migration")


asyncio.run(main())
