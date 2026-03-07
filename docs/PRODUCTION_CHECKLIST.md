# Production Checklist — перед запуском

Проверить все пункты перед первым production-запуском и перед каждым деплоем.

## Secrets

| Пункт | Статус |
|-------|--------|
| `SECRET_KEY` — сгенерирован, не дефолтный | ☐ |
| `ENCRYPTION_KEY` — Fernet key, не дефолтный | ☐ |
| `TELEGRAM_WEBHOOK_SECRET` — задан (для webhook mode) | ☐ |
| `POSTGRES_PASSWORD` — сильный пароль | ☐ |

## Webhook

| Пункт | Статус |
|-------|--------|
| Webhook secret настроен в .env | ☐ |
| Telegram webhook URL указан с секретом в заголовке | ☐ |

## Security

| Пункт | Статус |
|-------|--------|
| CSRF включён (по умолчанию) | ☐ |
| Secure cookies включены (prod) | ☐ |
| CORS trusted origins заданы (без `*`) | ☐ |
| Rate limits включены | ☐ |
| Billing limits включены | ☐ |

## Infrastructure

| Пункт | Статус |
|-------|--------|
| DB reachable (pg_isready) | ☐ |
| Redis reachable (ping) | ☐ |
| Migrations applied | ☐ |
| Health/ready/live endpoints отвечают | ☐ |

## Observability

| Пункт | Статус |
|-------|--------|
| Metrics available (`/metrics`) | ☐ |
| Structured logging (JSON в prod) | ☐ |

## Auth

| Пункт | Статус |
|-------|--------|
| WS auth — cookie-only (no localStorage token) | ☐ |
| Frontend не хранит token в localStorage | ☐ |

## Backup & SSL

| Пункт | Статус |
|-------|--------|
| Backup настроен (cron) | ☐ |
| SSL/domain настроен | ☐ |

---

**Проверка health после старта:**
```bash
curl -s http://localhost:8002/health
curl -s http://localhost:8002/ready
curl -s http://localhost:8002/live
```
