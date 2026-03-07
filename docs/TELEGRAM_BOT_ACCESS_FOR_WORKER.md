# Telegram Bot Access for Worker

Как worker получает доступ к боту для отправки reminders. Контракт без ловушки «worker не может слать Telegram без bot_main».

---

## Current state

**Откуда NotificationService берёт bot instance:**

```python
from app.bot.loader import bot
```

`app.bot.loader` создаёт глобальный singleton при импорте модуля:

```python
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
```

**Зависимости:**

| Компонент | Зависит от bot_main.py? | Зависит от polling? |
|-----------|-------------------------|---------------------|
| `bot` (Bot instance) | нет | нет |
| `dp` (Dispatcher) | нет | да (только для приёма updates) |

**Важно:** `Bot` из aiogram — это HTTP-клиент к Telegram API. `bot.send_message()` работает без polling. Polling (`dp.start_polling(bot)`) нужен только для приёма сообщений. Отправка — отдельная операция.

**Побочный эффект:** При импорте `app.bot.loader` также вызывается `_make_storage()` для `dp` (Redis FSM). Worker не использует `dp`, но импорт loader выполняет этот код. При недоступности Redis используется MemoryStorage — worker всё равно может стартовать.

---

## Target rule

- Worker должен уметь отправлять Telegram-сообщения **без** запуска bot polling/webhook process.
- Bot client должен инициализироваться как **зависимость/loader**, а не через запуск всего бота.
- Worker импортирует `from app.bot.loader import bot` и вызывает `bot.send_message()` — этого достаточно. Polling не требуется.

---

## Decision

**Один источник bot instance для API, worker и bot handlers:**

| Компонент | Источник bot | Polling |
|-----------|--------------|---------|
| API (webhook) | `app.bot.loader` | нет (webhook принимает updates) |
| Worker | `app.bot.loader` | нет |
| Bot handlers (bot_main) | `app.bot.loader` | да |

**Итог:** Worker использует тот же `app.bot.loader`, что и API. Запуск `bot_main.py` для worker **не требуется**. Достаточно `python -m app.worker` — при импорте NotificationService загрузится loader, создастся `bot`, reminders смогут слать сообщения.
