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
