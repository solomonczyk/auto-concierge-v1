# Worker Runtime Contract

Контракт запуска worker: entrypoint, startup, зависимости, observability.

---

## Entrypoint

**Канонический способ запуска:**

```
python -m app.worker
```

Один entrypoint. Docker, systemd и docker-compose используют только его.

---

## Startup behavior

При старте worker выполняет:

1. **Init scheduler** — создаёт `AsyncIOScheduler` с timezone из `SHOP_TIMEZONE`.
2. **Register jobs** — добавляет 4 задачи (см. WORKER_ARCHITECTURE_DECISION.md).
3. **Start loop** — scheduler запускается, процесс блокируется в бесконечном цикле или `asyncio.run()`.
4. **Graceful shutdown** — при SIGTERM/SIGINT останавливает scheduler, завершает незавершённые задачи, выходит с кодом 0.

---

## Required dependencies

| Зависимость | Нужна | Причина |
|-------------|-------|---------|
| **DB** (PostgreSQL) | да | Все 4 задачи читают/пишут в БД. |
| **Redis** | нет | Worker не обслуживает HTTP, WebSocket, rate limit. Redis не используется. |
| **Telegram bot token** | да | `send_evening_reminders` и `send_morning_reminders` шлют сообщения через `NotificationService` → `bot.send_message`. |

---

## Health / observability

Worker обязан логировать:

| Событие | Уровень | Пример |
|---------|---------|--------|
| Startup | INFO | `worker.started scheduler=apscheduler jobs=4` |
| Job started | INFO | `worker.job_started job_id=auto_no_show` |
| Job finished | INFO | `worker.job_finished job_id=auto_no_show result=...` |
| Job failed | ERROR | `worker.job_failed job_id=auto_no_show error=...` |
| Shutdown | INFO | `worker.shutdown reason=sigterm` |

Структурированные логи (JSON) — опционально, для production.
