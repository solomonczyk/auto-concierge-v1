import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import User
from app.core.security import get_password_hash
from sqlalchemy import select

async def create_admin():
    db_url = "postgresql+asyncpg://postgres:SecureP@ssw0rd2024!@db/autoservice"
    engine = create_async_engine(db_url, echo=False)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Check if admin exists
        result = await session.execute(select(User).where(User.username == "admin"))
        existing = result.scalar_one_or_none()
        
        if existing:
            print("Admin user already exists!")
        else:
            # Create admin user
            admin = User(
                username="admin",
                full_name="Admin User",
                email="admin@autoservice.local",
                hashed_password=get_password_hash("admin"),
                is_active=True,
                role="admin"
            )
            session.add(admin)
            await session.commit()
            print("Admin user created successfully!")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_admin())
