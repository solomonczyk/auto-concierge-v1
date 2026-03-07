# Release Flow — безопасный порядок деплоя

## Production launch sequence

1. **Backup** — создать бэкап PostgreSQL (см. `docs/BACKUP_RESTORE.md`)
   ```bash
   ./scripts/run_backup_now.sh
   ```

2. **Migrate** — применить миграции (api container: WORKDIR /app, alembic.ini в корне)
   ```bash
   docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
   ```

3. **Restart app** — пересобрать и перезапустить
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

4. **Smoke check** — проверить health и ключевые endpoints
   ```bash
   curl -s http://localhost:8002/health | jq .
   curl -s http://localhost:8002/ready | jq .
   curl -s http://localhost:8002/live | jq .
   ```

---

## Rollback flow

1. **Остановить новые контейнеры**
   ```bash
   docker compose -f docker-compose.prod.yml down
   ```

2. **Откатить миграции** (если применялись)
   ```bash
   docker compose -f docker-compose.prod.yml run --rm api alembic downgrade -1
   ```

3. **Восстановить БД из backup** (если миграция сломала данные)
   ```bash
   # см. docs/BACKUP_RESTORE.md
   ```

4. **Вернуть предыдущую версию кода**
   ```bash
   git checkout <previous-commit>
   ```

5. **Запустить старую версию**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

6. **Smoke check** — убедиться, что всё работает
