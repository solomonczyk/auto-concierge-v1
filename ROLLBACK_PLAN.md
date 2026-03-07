# Rollback Plan — Auto-Concierge

## 1. Disable Problematic Webhook

```bash
# Immediately stop processing Telegram updates
# Option A: Unset webhook via Telegram API
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"

# Option B: Set TELEGRAM_WEBHOOK_SECRET to empty → returns 503 automatically in production
```

## 2. Rollback Database Migration

```bash
# Check current revision
alembic current

# Rollback one step
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>
```

**Important**: Always check `alembic history` before downgrading to confirm target revision.

## 3. Disable External Integration

External integration is already hardened:
- `enqueue_appointment()` never raises — failures are logged and ignored
- If Redis/RQ is down, appointment creation still succeeds

To fully disable:
```bash
# Stop RQ worker
supervisorctl stop rq-worker
# or
docker stop autoconcierge-rq-worker
```

Appointments will queue in Redis but won't sync until worker restarts.

## 4. Survive Redis Failure

- `/health` returns `"redis": "degraded"` → monitoring alerts
- WS connections will fail (ticket anti-replay requires Redis)
- Appointments that don't need slot locking will still work
- Webhook idempotency check will fail → duplicates possible but not critical

**Recovery**: Restart Redis, no data migration needed (all Redis data is ephemeral).

## 5. Rollback Application Code

```bash
# On the server
cd /path/to/auto-concierge
git log --oneline -5  # find last known good commit

git checkout <good_commit_hash>
docker compose -f docker-compose.prod.yml up -d --build backend
# or
supervisorctl restart autoconcierge
```

## 6. Emergency: Cookie Auth Rollback

If cookie-based auth has issues:
- Backend `deps.py` still supports `Authorization: Bearer` header as fallback
- Swagger / API clients work without cookies
- For frontend: revert `AuthContext.tsx` to localStorage-based version from git history

## Quick Decision Tree

```
Problem?
├── Webhook spammed/attacked → Delete webhook (step 1)
├── Migration broke schema  → alembic downgrade (step 2)
├── External sync flooding  → Stop RQ worker (step 3)
├── Redis down              → Wait for recovery (step 4)
├── App crash on startup    → git checkout + rebuild (step 5)
└── Auth broken             → Bearer header fallback (step 6)
```
