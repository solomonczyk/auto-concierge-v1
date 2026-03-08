# Runbook — incident guide

Краткие шаги при типовых инцидентах.

---

## DB down

1. Проверить контейнер: `docker ps -a | grep db`
2. Логи: `docker logs autoservice_db_prod`
3. Перезапуск: `docker compose -f docker-compose.prod.yml restart db`
4. Дождаться healthcheck (pg_isready)
5. API/worker/bot перезапустятся автоматически (depends_on)
6. Если volume повреждён — восстановить из backup (см. BACKUP_RESTORE.md)

---

## Redis down

1. Проверить: `docker ps -a | grep redis`
2. Логи: `docker logs autoservice_redis_prod`
3. Перезапуск: `docker compose -f docker-compose.prod.yml restart redis`
4. Потеря данных: FSM, кэш, RQ jobs. Сервис восстановится после старта Redis.
5. AOF включён — данные восстановятся из appendonly.aof при рестарте.

---

## Webhook rejects spike (403/503)

1. Проверить `TELEGRAM_WEBHOOK_SECRET` в .env — совпадает ли с заголовком `x-telegram-bot-api-secret-token`
2. Проверить rate limit (120/min) — не исчерпан ли
3. Логи API: `docker logs autoservice_api_prod`
4. Метрики: `curl -s http://localhost:8002/metrics | grep webhook`

---

## WS events stop arriving

1. Проверить Redis: `docker exec autoservice_redis_prod redis-cli ping`
2. Проверить подписку: API публикует в `appointments_updates:{tenant_id}`
3. Frontend: cookie с access_token, WS URL с тем же origin
4. Логи API при broadcast
5. Переподключить клиент (refresh страницы)

---

## Migrations failed

1. Не перезапускать API до исправления
2. Откатить: `alembic downgrade -1`
3. Исправить миграцию, протестировать локально
4. Применить заново: `alembic upgrade head`
5. Если данные повреждены — restore из backup

---

## Recovery Test (Backup Restore Verification)

**Назначение:** Один раз проверить, что restore из backup реально работает.

### Сценарий

1. Взять свежий backup
2. Поднять отдельную БД (или пересоздать тестовую)
3. Выполнить restore
4. Запустить backend
5. Проверить: login, чтение appointments, чтение clients

### Команды restore

```bash
# 1. Restore в тестовую БД autoservice_restore_test
docker exec -i autoservice_db_prod psql -U postgres -c "CREATE DATABASE autoservice_restore_test;"
docker cp backups/baseline_2026_03_07.dump autoservice_db_prod:/tmp/
docker exec -i autoservice_db_prod pg_restore -U postgres -d autoservice_restore_test --no-owner --no-acl /tmp/baseline_2026_03_07.dump

# 2. ОБЯЗАТЕЛЬНО: Миграции (backup старее кода)
$env:BACKEND_CORS_ORIGINS='["http://localhost:5173"]'  # PowerShell
docker compose -f docker-compose.prod.yml run --rm -e POSTGRES_DB=autoservice_restore_test -e ENVIRONMENT=development api alembic upgrade head

# 4. Запуск API на restore_test (порт 8003)
docker compose -f docker-compose.prod.yml run --rm -d -p 8003:8000 -e POSTGRES_DB=autoservice_restore_test -e ENVIRONMENT=development api

# 5. Проверка: POST login, GET appointments, GET clients
```

**Важно:** Backup из прошлых версий не содержит колонок новых миграций. Без `alembic upgrade head` API упадёт с `column X does not exist`.

### Результат теста (выполнен 2026-03-08)

| Поле | Значение |
|------|----------|
| **Дата теста** | 2026-03-08 |
| **Backup файл** | `backups/baseline_2026_03_07.dump` |
| **Куда восстанавливали** | `autoservice_restore_test` |
| **Backend поднялся** | да |
| **Login** | OK (200) |
| **GET /appointments** | OK (200, []) |
| **GET /clients** | OK (200, []) |

**Поправки:** baseline имел схему f9a0b1c2d3e4 → выполнен `alembic upgrade head`, вручную добавлены миграции d1e2f3a4b5c6, e2f3a4b5c6d7 и недостающие колонки clients. Для login создан тестовый user (backup пустой).
