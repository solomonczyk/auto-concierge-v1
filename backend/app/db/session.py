from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import logging
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

from app.core.context import tenant_id_context

logger = logging.getLogger(__name__)

async def get_db():
    async with async_session_local() as session:
        tenant_id = tenant_id_context.get()
        if tenant_id is not None:
            try:
                # SET does not support bound params; tenant_id is from our context (int)
                tid = str(int(tenant_id))
                await session.execute(text(f"SET LOCAL app.current_tenant_id = '{tid}'"))
            except Exception as exc:
                logger.warning(f"Failed to set app.current_tenant_id: {exc}")
        try:
            # We don't manage the transaction here to allow handlers
            # to commit/rollback as needed.
            yield session
        finally:
            try:
                await session.execute(text("RESET app.current_tenant_id"))
            except Exception:
                # Non-Postgres/test backends may not support this setting.
                pass
