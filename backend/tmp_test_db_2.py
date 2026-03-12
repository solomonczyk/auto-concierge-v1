import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_db():
    # Try 5432 with password from root .env
    uri = "postgresql+asyncpg://postgres:SecureP@ssw0rd2024!@localhost:5432/autoservice"
    engine = create_async_engine(uri)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("Database connection successful on port 5432 with SecureP@ssw0rd2024!!")
    except Exception as e:
        print(f"Database connection failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_db())
