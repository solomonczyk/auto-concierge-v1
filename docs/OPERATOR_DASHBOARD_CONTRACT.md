# Operator Dashboard Contract

Контракт операторского дашборда для v1. Фиксирует виджеты, источники данных, действия и границы.

---

## Main widgets

| Виджет | Описание |
|--------|----------|
| **Today appointments** | Записи на сегодня: список/календарь по выбранной дате |
| **Kanban board** | Доска: waitlist → new → confirmed → in_progress → completed |
| **Waiting list** | Лист ожидания (колонка Kanban или отдельный блок) |
| **Cancelled / no_show section** | Архив: отменённые и неявившиеся (terminal статусы) |
| **SLA alerts** | Алерты: не подтверждённые >15 мин, риск no_show |

---

## Data sources

| Блок | Источник данных |
|------|-----------------|
| **Today appointments** | `GET /api/v1/appointments/?date=YYYY-MM-DD` (или фильтр на клиенте из общего списка) |
| **Kanban** | `GET /api/v1/appointments/kanban` + WS `appointments_updates:{tenant_id}` |
| **Waiting list** | Часть Kanban (колонка waitlist) или тот же appointments с `status=waitlist` |
| **Cancelled / no_show** | `GET /api/v1/appointments/` + фильтр `status in (cancelled, no_show)` на клиенте |
| **SLA alerts** | Backend aggregated endpoint (например `GET /api/v1/sla/unconfirmed`) или отдельный alerts endpoint. Сейчас worker только логирует — нужен API для отображения в UI. |

---

## Kanban API contract

1. **Endpoint:** `GET /api/v1/appointments/kanban`

2. **Возвращает только статусы Kanban:** waitlist, new, confirmed, in_progress, completed

3. **Terminal статусы не возвращаются:** cancelled, no_show

---

## Actions available to operator

| Действие | Переход | Роль |
|----------|---------|------|
| **confirm** | new → confirmed | Admin, Manager |
| **start work** | confirmed → in_progress | Admin, Manager |
| **complete** | in_progress → completed | Admin, Manager, Staff |
| **cancel** | * → cancelled | Admin, Manager |
| **promote from waitlist** | waitlist → new | Admin |

---

## Out of scope for v1

- analytics
- finance
- deep reporting
- multi-branch overview
