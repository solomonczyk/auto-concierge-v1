# Notification Call Sites — Инвентаризация

Все точки отправки уведомлений. Appointment-события идут через `NotificationService.dispatch()`.

---

## Таблица call sites

| file | function / endpoint | current call | channel | event assumption | status |
|------|--------------------|--------------|---------|------------------|--------|
| `backend/app/api/endpoints/appointments.py` | `update_appointment_status` (PATCH `/{id}/status`) | `NotificationService.dispatch` | Telegram | appointment_confirmed / cancelled / no_show | ✅ dispatch |
| `backend/app/api/endpoints/appointments.py` | `create_public_appointment` (POST `/public`) | `NotificationService.dispatch` | Telegram | appointment_created (client + manager) | ✅ dispatch |
| `backend/app/api/endpoints/public.py` | `create_public_appointment` (POST `/{slug}/appointments/public`) | `NotificationService.dispatch` | Telegram | appointment_created (client + manager) | ✅ dispatch |
| `backend/app/bot/handlers.py` | `cancel_appointment_handler` (callback) | `NotificationService.dispatch` | Telegram | appointment_cancelled | ✅ dispatch |
| `backend/app/bot/handlers.py` | `web_app_data_handler` (WebApp submit) | `NotificationService.dispatch` | Telegram | appointment_created (manager) | ✅ dispatch |
| `backend/app/services/reminder_service.py` | `send_evening_reminders` | `NotificationService.send_raw_message` | Telegram | reminder_evening (не appointment event) | review_later |
| `backend/app/services/reminder_service.py` | `send_morning_reminders` | `NotificationService.send_raw_message` | Telegram | reminder_morning (не appointment event) | review_later |
| `backend/app/services/demo_workflow.py` | `send_tg` | `NotificationService.send_raw_message` | Telegram | demo flow (не appointment event) | review_later |
| `backend/app/services/notification_service.py` | `send_raw_message` | `bot.send_message` | Telegram | — | keep_as_internal_adapter |
| `backend/app/services/notification_service.py` | `send_booking_confirmation` | `bot.send_message` | Telegram | — | keep_as_internal_adapter |
| `backend/app/services/notification_service.py` | `notify_admin` | `bot.send_message` | Telegram | — | keep_as_internal_adapter |
| `backend/app/services/notification_service.py` | `notify_client_status_change` | `bot.send_message` | Telegram | — | keep_as_internal_adapter |
| `backend/tests/conftest.py` | `mock_redis_notifications_ratelimit` | patch `send_booking_confirmation`, `notify_admin`, `notify_client_status_change` | — | test setup | review_later |

---

## Прямые вызовы `bot.send_message` вне NotificationService

**Нет активных нарушений.**

- Прямых вызовов `bot.send_message` вне `NotificationService` нет.
- `_notify_admin` удалена (ранее обходила сервис в `bot/handlers.py`).
- Все appointment events маршрутизируются через `NotificationService.dispatch(...)`.

---

## Примечания
- **keep_as_internal_adapter** — методы `NotificationService` станут внутренними адаптерами, вызываемыми только из `dispatch`.
- **review_later** — reminders, demo, test mocks — не appointment events; решить при расширении контракта (отдельные event types или оставить как есть).
