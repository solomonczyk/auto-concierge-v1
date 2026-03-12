# Outbox Worker — Runtime & Lifecycle

1. **`run_outbox_worker()`** запускается в фоне через lifespan FastAPI.

2. **Запуск guarded** через `ENABLE_OUTBOX_WORKER` (по умолчанию `false`).

3. **Task** хранится в `app.state.outbox_worker_task`.

4. **На shutdown** task отменяется до закрытия Redis/DB.
