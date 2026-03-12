import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_db():
    # Use 127.0.0.1 to avoid getaddrinfo issues
    uri = "postgresql+asyncpg://postgres:SecureP@ssw0rd2024!@127.0.0.1:5432/autoservice"
    engine = create_async_engine(uri)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("Database connection successful on 127.0.0.1:5432!")
    except Exception as e:
        print(f"Database connection failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_db())
