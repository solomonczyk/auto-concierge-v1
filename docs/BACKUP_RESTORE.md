# Backup / Restore Strategy

## PostgreSQL backup

```bash
# Создать директорию для бэкапов
mkdir -p /var/backups/auto-concierge

# Ручной бэкап (gzip)
docker exec autoservice_db_prod pg_dump -U postgres autoservice | gzip > /var/backups/auto-concierge/autoservice_$(date +%F_%H%M).sql.gz
```

Или использовать скрипт:
```bash
./scripts/run_backup_now.sh
```

## PostgreSQL restore

```bash
# 1. Остановить API и worker (чтобы не было активных соединений)
docker compose -f docker-compose.prod.yml stop api worker bot

# 2. Восстановить из backup
gunzip -c /var/backups/auto-concierge/autoservice_YYYY-MM-DD.sql.gz | docker exec -i autoservice_db_prod psql -U postgres -d autoservice

# 3. Запустить сервисы
docker compose -f docker-compose.prod.yml start api worker bot
```

**Важно:** при полном restore в существующую БД может потребоваться `--clean` в pg_restore или пересоздание БД. Для pg_dump plain SQL:
```bash
# Пересоздать БД (осторожно — потеря данных!)
docker exec -i autoservice_db_prod psql -U postgres -c "DROP DATABASE autoservice;"
docker exec -i autoservice_db_prod psql -U postgres -c "CREATE DATABASE autoservice;"
gunzip -c backup.sql.gz | docker exec -i autoservice_db_prod psql -U postgres -d autoservice
```

## Redis

- **Redis:** не бэкапим по умолчанию. Содержит: FSM, кэш WS-тикетов, дедупликацию webhook, RQ очереди.
- **При падении Redis:** данные теряются. FSM сбросится, RQ jobs потеряются. Сервис продолжит работать после перезапуска Redis.
- **AOF включён** (`redis-server --appendonly yes`) — при перезапуске контейнера Redis восстановит данные из AOF.
- **Бэкап Redis (опционально):** `docker exec autoservice_redis_prod redis-cli BGSAVE` — создаёт RDB в `/data/dump.rdb`. Копировать volume при необходимости.

## Где храним backup

- **Путь:** `/var/backups/auto-concierge/`
- **Формат имени:** `autoservice_YYYY-MM-DD.sql.gz` или `autoservice_YYYY-MM-DD_HHMM.sql.gz`
- **Рекомендация:** копировать на внешнее хранилище (S3, другой сервер) по расписанию.

## Как часто делаем backup

- **Рекомендация:** ежедневно в 03:00 (cron)
- **Перед деплоем:** обязательно ручной backup
- **Retention:** хранить минимум 7 дней, лучше 30.

```bash
# Настроить cron (пример)
./scripts/setup_backup_cron.sh
# или вручную:
# 0 3 * * * /path/to/run_backup_now.sh
```
