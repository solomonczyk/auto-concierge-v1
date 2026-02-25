#!/bin/bash

echo "=== Auto Concierge Deployment Fix Script ==="
echo "This script should be run on the server: ssh root@109.172.114.149"

# Navigate to project directory
cd /root/auto-concierge-v1

echo "1. Checking current container status..."
docker-compose -f docker-compose.prod.yml ps

echo "2. Running Alembic migrations to create database schema..."
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

echo "3. Creating test user if needed..."
docker-compose -f docker-compose.prod.yml exec api python -c "
import asyncio
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.models import User
from app.core.security import get_password_hash

async def create_test_user():
    async with SessionLocal() as session:
        # Check if test user already exists
        result = await session.execute(
            'SELECT id FROM users WHERE email = \"test@example.com\"'
        )
        existing_user = result.scalar_one_or_none()
        
        if not existing_user:
            # Create test user
            test_user = User(
                email='test@example.com',
                hashed_password=get_password_hash('testpass123'),
                full_name='Test User',
                is_active=True,
                is_superuser=False
            )
            session.add(test_user)
            await session.commit()
            print('Test user created: test@example.com / testpass123')
        else:
            print('Test user already exists')

asyncio.run(create_test_user())
"

echo "4. Testing login API..."
curl -X POST "http://localhost:8000/api/v1/login/access-token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=test@example.com&password=testpass123"

echo ""
echo "=== Deployment fix complete ==="
echo "Test login credentials: test@example.com / testpass123"
echo "Frontend URL: https://bt-aistudio.ru/concierge/"
