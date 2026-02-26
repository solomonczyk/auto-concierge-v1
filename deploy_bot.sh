#!/bin/bash
set -e
cd /root/auto-concierge-v1

echo "=== 1. Updating WEBAPP_URL ==="
sed -i 's|WEBAPP_URL=.*|WEBAPP_URL=https://bt-aistudio.ru/concierge|' .env
grep WEBAPP_URL .env

echo "=== 2. Git stash + pull ==="
git stash || true
git fetch origin main
git reset --hard origin/main
echo "Git pull done"

echo "=== 3. Restore WEBAPP_URL after reset ==="
sed -i 's|WEBAPP_URL=.*|WEBAPP_URL=https://bt-aistudio.ru/concierge|' .env
grep WEBAPP_URL .env

echo "=== 4. Rebuild bot container ==="
docker compose -f docker-compose.prod.yml up -d --build bot

echo "=== 5. Wait for bot to start ==="
sleep 8

echo "=== 6. Bot logs ==="
docker logs autoservice_bot_prod --tail 40

echo "=== 7. Run DB migration ==="
docker exec autoservice_api_prod alembic upgrade head 2>&1 || echo "Migration might have already run"

echo "=== DONE ==="
