# SLA Execution Model

Модель запуска SLA-процессов: где, как и с какой частотой выполняются задачи.

---

## 1. Где запускаются SLA-процессы

**Текущее состояние:**

| Процесс | Механизм | Файл |
|---------|----------|------|
| Reminders (evening, morning) | APScheduler в `bot_main.py` | `backend/bot_main.py` |
| **check_unconfirmed_appointments** | **Не запускается** | — |
| **auto_no_show** | **Не запускается** | — |

**Проблема:** `check_unconfirmed_appointments` и `auto_no_show` определены в `sla_service.py`, но ни один scheduler их не вызывает. В production они не выполняются.

**Целевой механизм (на выбор):**

- **Вариант A:** APScheduler в том же процессе, что и API (FastAPI lifespan) — простой старт, но SLA умирает при падении API.
- **Вариант B:** Отдельный worker-процесс с APScheduler — SLA работает независимо от API и бота.
- **Вариант C:** Внешний cron / systemd timer — вызывает CLI-команду или HTTP endpoint.

---

## 2. Какие задачи выполняются

| Функция | Описание | Рекомендуемая frequency |
|---------|----------|-------------------------|
| `check_unconfirmed_appointments(db)` | Находит NEW-записи старше 15 мин, логирует для менеджера | каждые 5 минут |
| `auto_no_show(db)` | Переводит CONFIRMED в NO_SHOW, если `start_time` прошло | каждую 1 минуту |

**Reminders (уже работают в bot_main.py):**

| Функция | Описание | Frequency |
|---------|----------|-----------|
| `send_evening_reminders` | Напоминание на завтра | 20:00 (cron) |
| `send_morning_reminders` | Напоминание на сегодня | 08:00 (cron) |

---

## 3. Требование production

**SLA-задачи должны работать независимо от Telegram bot.**

- При падении бота SLA не должен останавливаться.
- `auto_no_show` и `check_unconfirmed` критичны для бизнес-логики (переходы статусов, аудит).
- Рекомендация: вынести SLA в отдельный worker или cron, не привязывать к процессу `bot_main.py`.

---

## Следующий шаг

Определить worker architecture для production: отдельный процесс, Docker-сервис или cron — чтобы SLA не зависел от API и бота.
