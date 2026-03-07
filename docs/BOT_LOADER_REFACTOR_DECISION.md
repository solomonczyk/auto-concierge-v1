# Bot Loader Refactor Decision

Решение по декомпозиции `app.bot.loader`: разделить bot client и bot runtime.

---

## Problem

`app.bot.loader` инициализирует больше, чем нужно worker-у:

- Worker-у нужен только **Bot** для отправки сообщений (reminders).
- При импорте loader worker тянет за собой:
  - **Dispatcher** (`dp`)
  - **FSM storage** (Redis или MemoryStorage)
  - Побочные подключения и зависимости

Это лишняя сцепка. Worker не принимает updates, не использует FSM. Риск: worker случайно потянет в себя лишний runtime бота.

---

## Decision

Разделить на два модуля:

| Модуль | Содержимое | Кто импортирует |
|--------|------------|-----------------|
| `app.bot.client` | Только `Bot` instance | NotificationService, API, worker |
| `app.bot.loader` | Dispatcher, storage, handlers | bot runtime (bot_main, webhook) |

**`app.bot.client`** — минимальный модуль:

```python
# Только Bot. Никакого dp, storage, Redis.
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)  # или None при ошибке
```

**`app.bot.loader`** — полный runtime:

```python
from app.bot.client import bot  # переиспользует client
# dp, storage, handlers — всё остальное
```

---

## Target imports

| Компонент | Импорт bot | Импорт loader |
|-----------|------------|---------------|
| NotificationService | `from app.bot.client import bot` | — |
| API (webhook) | — | `from app.bot.loader import bot, dp` |
| Worker | `from app.bot.client import bot` (через NotificationService) | — |
| bot_main | — | `from app.bot.loader import bot, dp` |

---

## Migration note

1. **Сначала** создать `app.bot.client` — вынести создание `bot` из loader.
2. **Потом** перевести NotificationService на `app.bot.client`.
3. **Потом** обновить loader: импортировать `bot` из client, оставить dp/storage.
4. **Потом** делать `app.worker` — он не потянет loader.

Порядок важен: client должен существовать до worker, чтобы worker не зависел от loader.
