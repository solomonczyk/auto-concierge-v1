# Notification Dispatch Rules

Единая точка маршрутизации уведомлений. Все каналы (Telegram, in-app, email) управляются через один orchestrator.

---

## 1. Единая точка входа

**Orchestrator:** `NotificationService.dispatch(event, payload)`

- Все уведомления по записям проходят через этот метод.
- Текущая реализация: несколько методов (`notify_admin`, `notify_client_status_change`, `send_booking_confirmation`) вызываются напрямую из endpoints и bot handlers.
- **Target design:** один метод `dispatch(event_type, payload)` — единственная точка входа. Внутри него — выбор каналов, получателей и формирование сообщений по контракту `APPOINTMENT_NOTIFICATION_CONTRACT.md`.

---

## 2. Что приходит на вход

**Минимальный payload:**

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `event_type` | str | да | `appointment_created`, `appointment_confirmed`, `appointment_cancelled`, `appointment_no_show` |
| `appointment_id` | int | да | ID записи |
| `tenant_id` | int | да | Тенант (для изоляции, rate limit, логирования) |
| `recipient_roles` | list[str] | опционально | `["client"]`, `["manager"]`, `["client", "manager"]` — по контракту |
| `recipient_ids` | dict | опционально | `{"client_telegram_id": 123, "manager_chat_id": 456}` — если уже известны |
| `context` | dict | опционально | `service_name`, `old_status`, `new_status`, `slot_time` — для формирования текста |

**Пример вызова (target):**

```python
await NotificationService.dispatch(
    event_type="appointment_confirmed",
    appointment_id=appt.id,
    tenant_id=tenant_id,
    recipient_roles=["client"],
    context={"service_name": appt.service.name, "new_status": "confirmed"},
)
```

---

## 3. Что сервис делает внутри

1. **Выбирает каналы по контракту** — смотрит `APPOINTMENT_NOTIFICATION_CONTRACT.md`: для данного `event_type` какие получатели и какие каналы (Telegram, in-app, email).
2. **Проверяет идемпотентность** — по `(event_type, appointment_id, recipient, channel)` не отправлять дубль (Redis/DB или in-memory за окно запроса).
3. **Отправляет по каналам** — вызывает внутренние адаптеры: `_send_telegram(...)`, `_send_in_app(...)`, `_send_email(...)`. Не экспортирует их наружу.
4. **Логирует результат** — `logger.info` / `logger.error` с `event_type`, `appointment_id`, `channel`, `success`/`failure`.

---

## 4. Что запрещено

| Запрет | Причина |
|--------|---------|
| Не вызывать Telegram (`bot.send_message`) напрямую из endpoint или bot handler | Все отправки только через `NotificationService.dispatch` (или его внутренние адаптеры). |
| Не дублировать routing-логику в разных местах | Кто получает и по какому каналу — только в контракте и в `dispatch`. |
| Не отправлять уведомление до успешного `commit` | Сначала `db.commit()`, потом `dispatch`. Иначе при rollback уйдёт уведомление о несостоявшемся событии. |
| Не добавлять новые каналы без обновления контракта | Контракт — источник правды. Код следует контракту. |

---

## Текущее состояние (as-is)

- `NotificationService` — есть, но без единого `dispatch`. Методы вызываются напрямую.
- Endpoints (`appointments`, `public`) и `bot/handlers` вызывают `notify_admin`, `notify_client_status_change`, `send_booking_confirmation` с разной логикой.
- `bot/handlers` использует `_notify_admin` → `bot.send_message` напрямую, минуя сервис.
- Идемпотентность не проверяется.
- Документ описывает **target design**. Рефакторинг кода — отдельный шаг после утверждения правил.
