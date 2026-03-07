# Stage 5: Deployment + Production Checklist — Deliverable

## Пути к файлам

### Deploy-файлы
- `docker-compose.prod.yml` — production compose (db, redis, api, worker, bot, frontend)
- `.env.example.production` — шаблон .env для production
- `scripts/run_backup_now.sh` — backup PostgreSQL
- `scripts/setup_backup_cron.sh` — настройка cron для backup

### Checklist / Runbook
- `docs/PRODUCTION_CHECKLIST.md` — чеклист перед запуском
- `docs/RUNBOOK.md` — incident guide (DB down, Redis down, webhook spike, WS stop, migrations failed)
- `docs/RELEASE_FLOW.md` — release flow + rollback
- `docs/BACKUP_RESTORE.md` — backup/restore strategy
- `docs/DEPLOYMENT.md` — как поднять, обновить, проверить

### Final smoke / E2E тесты
- `backend/tests/test_smoke_e2e.py` — `test_full_client_journey`
- `frontend/e2e/*.spec.ts` — Playwright E2E (auth-ui, dashboard, webapp-booking, bot-webhook)

---

## Имена smoke/E2E тестов

| Тест | Описание |
|------|----------|
| `test_full_client_journey` | Login → /me → create appointment → patch status → WS → webhook → logout |

---

## Production launch sequence

1. **Backup** — `./scripts/run_backup_now.sh`
2. **Migrate** — `docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head`
3. **Restart** — `docker compose -f docker-compose.prod.yml up -d --build`
4. **Smoke** — `curl http://localhost:8002/health`, `/ready`, `/live`

---

## Rollback sequence

1. `docker compose -f docker-compose.prod.yml down`
2. `alembic downgrade -1` (если миграции ломают)
3. Восстановить БД из backup (см. BACKUP_RESTORE.md)
4. `git checkout <prev-commit>`
5. `docker compose -f docker-compose.prod.yml up -d --build`

---

## Backup/restore sequence

**Backup:**
```bash
./scripts/run_backup_now.sh
# → /var/backups/auto-concierge/autoservice_YYYY-MM-DD.sql.gz
```

**Restore:**
```bash
gunzip -c /var/backups/auto-concierge/autoservice_YYYY-MM-DD.sql.gz | docker exec -i autoservice_db_prod psql -U postgres autoservice
```

**Redis:** не бэкапим (ephemeral). При падении — перезапуск, FSM/кеш пересоздаются.

---

## Подтверждение: final smoke проходит

```
tests/test_smoke_e2e.py::test_full_client_journey PASSED
```

---

## Вне scope (осталось)

- SLA worker (`python -m app.worker`) — в prod используется RQ worker (`worker.py`); SLA-задачи (auto_no_show, check_unconfirmed) могут выполняться в bot (если bot_main включает scheduler) или требуют отдельного sla-worker
- Playwright E2E против production URL — требуют PLAYWRIGHT_BASE_URL, PLAYWRIGHT_ADMIN_PASS
- Nginx конфиг — пример в DEPLOYMENT.md, не включён в репо
- Мониторинг/алерты — Prometheus/Grafana не настроены
- SSL/домен — на стороне nginx/провайдера
