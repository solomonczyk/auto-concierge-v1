import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from urllib.parse import quote_plus

async def test_db():
    password = quote_plus("SecureP@ssw0rd2024!")
    uri = f"postgresql+asyncpg://postgres:{password}@127.0.0.1:5432/autoservice"
    print(f"Testing URI: {uri}")
    engine = create_async_engine(uri)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("Database connection successful!")
    except Exception as e:
        print(f"Database connection failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_db())
