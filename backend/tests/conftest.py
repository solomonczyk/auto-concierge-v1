import os
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import patch
from httpx import AsyncClient

# Patch starlette Config to skip .env on decode errors (Windows cp1252 vs UTF-8)
try:
    from starlette import config
    _orig_read = config.Config._read_file

    def _safe_read_file(self, path):
        try:
            return _orig_read(self, path)
        except UnicodeDecodeError:
            return {}

    config.Config._read_file = _safe_read_file
except Exception:
    pass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Test configuration - file-based SQLite for reliable cross-connection sharing
_test_db_path = os.path.join(os.path.dirname(__file__), "test.db")
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{_test_db_path}"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

test_async_session = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Mock settings for tests (Pydantic v2 compatible)
from app.core.config import Settings

test_settings = Settings(
    POSTGRES_SERVER="localhost",
    POSTGRES_USER="test",
    POSTGRES_PASSWORD="test",
    POSTGRES_DB="test",
    REDIS_HOST="localhost",
    SECRET_KEY="test-secret-key-for-testing",
    ENCRYPTION_KEY=None,
    ENVIRONMENT="test",
    TELEGRAM_BOT_TOKEN="123456789:AABBCCDDEEFFaabbccddeeff",
    PUBLIC_TENANT_ID=1,
)

# Override settings before importing app
import app.core.config as config_module
config_module.settings = test_settings

from unittest.mock import AsyncMock, MagicMock, patch

from app.db.session import Base, get_db
from app.main import app
from app.models.models import User, Shop, Service, TariffPlan, Tenant, TenantStatus, UserRole
from app.core.security import get_password_hash


# Create tables for tests (sync wrapper for session scope)
@pytest.fixture(scope="session")
def create_tables():
    async def _create():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _drop():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_create())
        yield
    finally:
        loop.run_until_complete(_drop())
        loop.close()


# Override get_db dependency
async def override_get_db():
    async with test_async_session() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

# Disable rate limiter for tests (avoids 429 on repeated login)
from app.api.endpoints import login
login.limiter.enabled = False


@pytest.fixture(autouse=True)
def mock_redis_notifications_ratelimit():
    """Mock Redis, NotificationService, and disable rate limit for tests."""
    fake_redis = MagicMock()
    fake_redis.set = AsyncMock(return_value=True)
    fake_redis.delete = AsyncMock(return_value=None)
    fake_redis.publish = AsyncMock(return_value=1)
    with patch("app.api.endpoints.appointments.RedisService") as mock_redis_svc:
        mock_redis_svc.get_redis.return_value = fake_redis
        with patch("app.api.endpoints.ws.RedisService", mock_redis_svc):
            with patch("app.services.notification_service.NotificationService.send_booking_confirmation", new_callable=AsyncMock):
                with patch("app.services.notification_service.NotificationService.notify_admin", new_callable=AsyncMock):
                    with patch("app.services.notification_service.NotificationService.notify_client_status_change", new_callable=AsyncMock):
                        with patch("app.api.endpoints.appointments.external_integration.enqueue_appointment", new_callable=AsyncMock):
                            yield


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session(create_tables) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test"""
    async with test_async_session() as session:
        # Clean previous test data (file-based DB persists across tests)
        for table in ("appointments", "clients", "services", "users", "shops", "tenants", "tariff_plans"):
            try:
                await session.execute(text(f"DELETE FROM {table}"))
            except Exception:
                pass
        await session.commit()

        # Begin transaction for seeding
        async with session.begin():
            # Create test tariff plan
            tariff = TariffPlan(
                name="free",
                max_appointments=10,
                max_shops=1,
                is_active=True
            )
            session.add(tariff)
            await session.flush()  # get tariff.id

            # Create test tenant
            tenant = Tenant(
                id=1,
                name="Test Tenant",
                status=TenantStatus.ACTIVE,
                tariff_plan_id=tariff.id
            )
            session.add(tenant)
            await session.flush()  # get tenant.id
            
            # Create test shop with required tenant_id
            shop = Shop(
                tenant_id=1,
                name="Test Shop",
                address="Test Address",
                phone="+1234567890"
            )
            session.add(shop)
            await session.flush()

            # Create test service (required for appointments and public workflow)
            service = Service(
                tenant_id=1,
                name="Диагностика ходовой",
                duration_minutes=60,
                base_price=1500.0
            )
            session.add(service)
            await session.flush()

            # Create test user (shop_id links admin to shop for create_appointment)
            user = User(
                username="admin",
                hashed_password=get_password_hash("admin"),
                is_active=True,
                role=UserRole.ADMIN,
                tenant_id=1,
                shop_id=shop.id
            )
            session.add(user)

            await session.commit()
        
        yield session
        
        # Rollback transaction after test
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide HTTP client for API testing"""
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


# Helper to create a user and get token
@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    """Get token for admin user"""
    response = await client.post(
        "/api/v1/login/access-token",
        data={"username": "admin", "password": "admin"},
        headers={"content-type": "application/x-www-form-urlencoded"}
    )
    return response.json()["access_token"]


@pytest.fixture
async def auth_headers(admin_token: str) -> dict:
    """Get authorization headers"""
    return {"Authorization": f"Bearer {admin_token}"}
