# Этап 2: Production Infrastructure — Deliverable

## Реализовано

### 1. Health endpoints

| Endpoint | Методы | Описание |
|----------|--------|----------|
| `GET /health` | GET, HEAD | Общий статус: проверяет DB и Redis, 500 при degraded |
| `GET /live` | GET, HEAD | Liveness: приложение живо, без проверок зависимостей |
| `GET /ready` | GET, HEAD | Readiness: DB и Redis должны быть доступны, 503 при недоступности |

**Readiness contract:**
- DB недоступна → `checks.db` = `"unavailable: <ErrorType>"`, status 503
- Redis недоступен → `checks.redis` = `"unavailable: <ErrorType>"`, status 503
- Ответ содержит `checks`, `elapsed_ms`, `project`

### 2. Production config validation (fail-fast)

Обязательные переменные в production (`ENVIRONMENT=production`):
- `SECRET_KEY` — не пустой, не `dev-secret-key-change-in-production`
- `TELEGRAM_WEBHOOK_SECRET` — обязательно
- `ENCRYPTION_KEY` — обязательно
- Wildcard CORS с credentials — запрещён (ValueError при старте)

### 3. Graceful shutdown

В lifespan приложения:
- Закрытие Redis connections (`RedisService.close()`)
- Dispose DB engine (`engine.dispose()`)
- Без подвисаний при остановке

### 4. Production Docker / compose

- `docker-compose.prod.yml` — production compose
- Healthcheck для api: `GET /ready` (readiness)
- Healthcheck для db: `pg_isready`
- Healthcheck для redis: `redis-cli ping`
- `depends_on` с `condition: service_healthy` для db и redis

### 5. .env.example

- Обязательные переменные для production
- Комментарии по генерации SECRET_KEY, ENCRYPTION_KEY

---

## Пути к файлам

### Backend (изменённые)

| Файл | Описание |
|------|----------|
| `backend/app/main.py` | /health, /live, /ready, graceful shutdown в lifespan |
| `backend/app/core/config.py` | Production fail-fast: SECRET_KEY placeholder check |

### Infra / config

| Файл | Описание |
|------|----------|
| `docker-compose.prod.yml` | Production compose, healthchecks для api/db/redis |
| `backend/.env.example` | Шаблон env с production-переменными |

### Тесты

| Файл | Описание |
|------|----------|
| `backend/tests/test_infra.py` | Health, live, ready, DB/Redis down, config fail-fast |
| `backend/tests/conftest.py` | async_session_local, RedisService для health endpoints |

---

## Новые env-переменные (production)

| Переменная | Обязательна в prod | Описание |
|------------|---------------------|----------|
| `ENVIRONMENT` | — | `production` для prod-режима |
| `SECRET_KEY` | да | Секретный ключ, не dev placeholder |
| `TELEGRAM_WEBHOOK_SECRET` | да | Секрет для webhook |
| `ENCRYPTION_KEY` | да | Fernet key для шифрования |
| `POSTGRES_SERVER` | да | Хост PostgreSQL |
| `POSTGRES_USER` | да | Пользователь |
| `POSTGRES_PASSWORD` | да | Пароль |
| `POSTGRES_DB` | да | Имя БД |
| `REDIS_HOST` | да | Хост Redis |

---

## Список тестов

| Тест | Assert |
|------|--------|
| `test_health_returns_success` | GET /health → 200, status=ok, checks.db=ok, checks.redis=ok |
| `test_live_returns_success` | GET /live → 200, status=ok |
| `test_ready_returns_success_when_deps_available` | GET /ready → 200, checks.db=ok, checks.redis=ok |
| `test_ready_reflects_db_unavailable` | DB down → GET /ready 503, checks.db содержит "unavailable" |
| `test_ready_reflects_redis_unavailable` | Redis down → GET /ready 503, checks.redis содержит "unavailable" |
| `test_production_config_fail_fast_missing_secret` | SECRET_KEY=dev placeholder в prod → ValueError |
| `test_production_config_fail_fast_missing_encryption_key` | ENCRYPTION_KEY отсутствует в prod → ValueError |

---

## Примеры ответов

### GET /health (успех)

```json
{
  "status": "ok",
  "project": "Autoservice MVP",
  "checks": {"db": "ok", "redis": "ok"},
  "elapsed_ms": 5
}
```

### GET /live

```json
{
  "status": "ok",
  "project": "Autoservice MVP"
}
```

### GET /ready (успех)

```json
{
  "status": "ok",
  "project": "Autoservice MVP",
  "checks": {"db": "ok", "redis": "ok"},
  "elapsed_ms": 4
}
```

### GET /ready (DB недоступна, 503)

```json
{
  "status": "not_ready",
  "project": "Autoservice MVP",
  "checks": {"db": "unavailable: ConnectionRefused", "redis": "ok"},
  "elapsed_ms": 2
}
```

### GET /ready (Redis недоступен, 503)

```json
{
  "status": "not_ready",
  "project": "Autoservice MVP",
  "checks": {"db": "ok", "redis": "unavailable: ConnectionRefused"},
  "elapsed_ms": 3
}
```

---

## Запуск infra-тестов

```bash
cd backend
python -m pytest tests/test_infra.py -v
```

---

## Production launch sequence

1. Проверить `.env` по `backend/.env.example`
2. `docker compose -f docker-compose.prod.yml up -d`
3. Дождаться healthy статуса api (healthcheck /ready)
4. Проверить `GET /ready` вручную
