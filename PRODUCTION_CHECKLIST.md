# Production Checklist — Auto-Concierge

## Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | **yes** | ValueError on startup if missing in prod |
| `ENCRYPTION_KEY` | **yes** | ValueError on startup if missing in prod |
| `DATABASE_URL` / `POSTGRES_*` | **yes** | No defaults |
| `REDIS_HOST`, `REDIS_PORT` | **yes** | No defaults |
| `TELEGRAM_BOT_TOKEN` | **yes** | Bot won't start without it |
| `TELEGRAM_WEBHOOK_SECRET` | **yes** | ValueError on startup if missing in prod |
| `BACKEND_CORS_ORIGINS` | **yes** | No wildcards allowed with credentials in prod |
| `ENVIRONMENT` | recommended | Set to `production` |
| `ADMIN_CHAT_ID` | recommended | Admin notifications target |

## Database

- [ ] Alembic migrations applied: `alembic upgrade head`
- [ ] Check for multiple heads: `alembic heads` (should return 1)
- [ ] Seed admin user exists and can login
- [ ] Tenant(s) created with valid `slug`

## Redis

- [ ] Redis is reachable: `/health` returns `"redis": "ok"`
- [ ] RQ worker is running for background jobs

## Telegram

- [ ] Webhook URL configured via BotFather or `setWebhook`
- [ ] `TELEGRAM_WEBHOOK_SECRET` is set in both `.env` and webhook config
- [ ] Bot responds to `/start`

## Auth & Security

- [ ] Login returns `Set-Cookie: access_token` (HttpOnly, Secure, SameSite=Lax)
- [ ] `/me` returns user info from cookie
- [ ] `/auth/logout` clears cookie
- [ ] WS connects with `?ticket=...` only (legacy `?token=` rejected with 4401)
- [ ] Rate limits active: login 10/min, ws-ticket 30/min, webhook 120/min
- [ ] Swagger/OpenAPI disabled in production (`docs_url=None`)
- [ ] CORS: `allow_credentials=True`, no wildcard origins

## Metrics & Observability

- [ ] `/metrics` returns Prometheus text format
- [ ] `X-Request-ID` header present on all responses
- [ ] Key counters registered:
  - `ws_connections_total`, `ws_disconnect_total`
  - `ws_ticket_issued_total`, `ws_ticket_rejected_total`
  - `appointments_created_total`, `appointments_external_sync_failed_total`
  - `webhook_requests_total`, `webhook_rejected_total`, `webhook_processed_total`
- [ ] Logs contain: `request_id`, `tenant_id`, `event_type`
- [ ] No secrets in logs (JWT, cookies, headers, webhook secret)

## Graceful Degradation

- [ ] If Redis is down: health returns `degraded`, app doesn't crash
- [ ] If external integration fails: appointment still created, error logged
- [ ] If webhook downstream fails: returns 503, doesn't crash

## Rollback

See `ROLLBACK_PLAN.md` for step-by-step rollback procedures.
