# Auto-Concierge — Deployment Guide

## Как поднять систему

### 1. Подготовка

```bash
# Клонировать репозиторий
git clone <repo-url>
cd auto-concierge-v1

# Скопировать production env
cp .env.example.production .env
# Заполнить все CHANGE_ME / YOUR_* в .env
```

### 2. Порядок запуска

```bash
# 1. Инфраструктура (db, redis)
docker compose -f docker-compose.prod.yml up -d db redis

# 2. Дождаться healthcheck
docker compose -f docker-compose.prod.yml ps
# db и redis должны быть healthy

# 3. Миграции
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

# 4. Приложение
docker compose -f docker-compose.prod.yml up -d api worker bot frontend
```

### 3. Проверка

```bash
# Health
curl http://localhost:8002/health
curl http://localhost:8002/ready
curl http://localhost:8002/live

# Логи
docker compose -f docker-compose.prod.yml logs -f api
```

---

## Как обновить

```bash
git pull
docker compose -f docker-compose.prod.yml build --no-cache api worker bot frontend
# См. docs/RELEASE_FLOW.md — backup → migrate → restart → smoke
```

---

## Как проверить, что всё живо

| Проверка | Команда / URL |
|----------|---------------|
| API health | `curl http://localhost:8002/health` |
| API ready (DB+Redis) | `curl http://localhost:8002/ready` |
| Metrics | `curl http://localhost:8002/metrics` |
| Frontend | `curl -I http://localhost:8081` |
| Webhook | `curl -X POST http://localhost:8002/api/v1/webhook -H "Content-Type: application/json" -d '{"update_id":1,"message":{"message_id":1,"date":0,"chat":{"id":1,"type":"private"},"text":"/start"}}'` (может 403 если secret задан) |

---

## Nginx (пример)

```nginx
location /concierge/api/ {
    proxy_pass http://127.0.0.1:8002/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location /concierge/ {
    proxy_pass http://127.0.0.1:8081/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```
