from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Echo should only be True in development/debug mode
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI, 
    echo=settings.ENVIRONMENT.lower() == "development"
)

async_session_local = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

from sqlalchemy import text
from app.core.context import tenant_id_context

async def get_db():
    async with async_session_local() as session:
        # We don't manage the transaction here to allow handlers 
        # to commit/rollback as needed.
        yield session
