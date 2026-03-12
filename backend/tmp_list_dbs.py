import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def list_dbs():
    # Connect to the default 'postgres' database to list others
    uri = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres"
    engine = create_async_engine(uri)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false;"))
            dbs = [row[0] for row in result]
            print(f"Databases: {dbs}")
            if "autoservice" in dbs:
                print("Database 'autoservice' EXISTS.")
            else:
                print("Database 'autoservice' is MISSING.")
    except Exception as e:
        print(f"Failed to list databases: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(list_dbs())
