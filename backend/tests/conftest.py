import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

# Test configuration - use SQLite for fast tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

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

# Mock settings for tests
from app.core.config import Settings

class TestSettings(Settings):
    def __init__(self):
        # Set test values before calling parent __init__
        self.POSTGRES_SERVER = "localhost"
        self.POSTGRES_USER = "test"
        self.POSTGRES_PASSWORD = "test"
        self.POSTGRES_DB = "test"
        self.REDIS_HOST = "localhost"
        self.SECRET_KEY = "test-secret-key-for-testing"
        self.ENCRYPTION_KEY = None
        self.ENVIRONMENT = "test"
        self.TELEGRAM_BOT_TOKEN = "123456789:AABBCCDDEEFFaabbccddeeff"

# Override settings before importing app
import app.core.config as config_module
test_settings = TestSettings()

# Mock the settings module
config_module.settings = test_settings

from app.db.session import Base, get_db
from app.main import app
from app.models.models import User, Shop, TariffPlan
from app.core.security import get_password_hash


# Create tables for tests
@pytest.fixture(scope="session")
async def create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Override get_db dependency
async def override_get_db():
    async with test_async_session() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session(create_tables) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for each test"""
    async with test_async_session() as session:
        # Begin transaction
        async with session.begin():
            # Create test tariff plan
            tariff = TariffPlan(
                name="free",
                max_appointments=10,
                max_shops=1,
                is_active=True
            )
            session.add(tariff)
            
            # Create test shop
            shop = Shop(
                name="Test Shop",
                address="Test Address",
                phone="+1234567890"
            )
            session.add(shop)
            
            # Create test user
            user = User(
                username="admin",
                hashed_password=get_password_hash("admin"),
                is_active=True,
                role="admin",
                tenant_id=1
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
