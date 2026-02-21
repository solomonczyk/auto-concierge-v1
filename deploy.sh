#!/bin/bash
# Auto-Concierge v1.0 Production Deployment Script

echo "🚀 Starting Deployment of Auto-Concierge v1.0 (Hardened)..."

# 1. Pull latest changes (assuming git is set up)
# git pull origin main

# 2. Build and restart services
docker-compose -f docker-compose.prod.yml up -d --build

# 3. Run database migrations inside the API container
echo "🔄 Running migrations..."
docker exec autoservice_api_prod alembic upgrade head

# 4. Optional: Seed initial tariffs if new install
# docker exec autoservice_api_prod python seed_tariffs.py

echo "✅ Deployment complete!"
docker-compose -f docker-compose.prod.yml ps
