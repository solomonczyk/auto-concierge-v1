# Worker Architecture Decision

Архитектурное решение: отдельный worker-процесс для SLA и reminders.

---

## Decision

**SLA + reminders run in dedicated worker service.**

Отдельный процесс с APScheduler, не входящий в API и не входящий в Telegram bot.

---

## Why

- Не зависит от API — падение FastAPI не останавливает SLA.
- Не зависит от Telegram bot — падение бота не останавливает SLA.
- Проще мониторить и рестартовать отдельно — один процесс, одна ответственность.

---

## Worker responsibilities

| Задача | Frequency |
|--------|------------|
| `check_unconfirmed_appointments` | каждые 5 минут |
| `auto_no_show` | каждую 1 минуту |
| `send_evening_reminders` | 20:00 (cron) |
| `send_morning_reminders` | 08:00 (cron) |

---

## Non-responsibilities

- Не обслуживает HTTP.
- Не принимает WebSocket.
- Не хранит бизнес-логику endpoint-ов.
