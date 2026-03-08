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

| Block | Source |
|-------|--------|
| **Today appointments** | `GET /api/v1/appointments/today` |
| **Kanban** | `GET /api/v1/appointments/kanban` + WS `appointments_updates:{tenant_id}` |
| **Waiting list** | Часть Kanban (status=waitlist) |
| **Cancelled / no_show** | `GET /api/v1/appointments/terminal` |
| **SLA alerts** | `GET /api/v1/sla/unconfirmed` |

---

## Today appointments API contract

1. **Endpoint:** `GET /api/v1/appointments/today`

2. **Returns:** appointments for current day only (tenant timezone)

3. **Tenant isolation:** tenant_id filter

4. **Sorting:** start_time ASC

5. **Pagination:** skip, limit (1..100)

---

## Kanban API contract

1. **Data source:** `GET /api/v1/appointments/kanban` (+ WS `appointments_updates:{tenant_id}` для live updates)

2. **Response format:** объект с 5 колонками. Каждая колонка — массив `AppointmentRead`:

   ```json
   {
     "waitlist": [],
     "new": [],
     "confirmed": [],
     "in_progress": [],
     "completed": []
   }
   ```

3. **Правила:**
   - **cancelled** и **no_show** не входят в response (terminal статусы)
   - внутри каждой колонки сортировка **start_time ASC**
   - **tenant isolation** обязателен (фильтр по tenant_id)

---

## Terminal (Cancelled / no_show) API contract

1. **Endpoint:** `GET /api/v1/appointments/terminal`

2. **Statuses:** только cancelled, no_show

3. **Sorting:** created_at DESC (сверху самые свежие)

4. **Pagination:** skip, limit (limit 1..100)

---

## Appointment lifecycle history

1. **Endpoint:** `GET /api/v1/appointments/{appointment_id}/history`

2. **Sorting:** created_at ASC (хронологический порядок для UI lifecycle)

3. **Tenant isolation:** фильтр по tenant_id — история другого tenant не возвращается

4. **Response:** список записей с полями id, appointment_id, old_status, new_status, created_at, actor (username при изменении пользователем)

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
