# Client Action Consistency Layer — Audit & Implementation

## Цель контура
После client actions (cancel, reschedule) WebApp получает свежее, консистентное, UI-safe состояние записи без доп. запроса.

---

## Шаг 1. Public cancel → fresh snapshot response

### Текущее состояние

| Endpoint | Файл | Response Model | Snapshot? | Метод |
|----------|------|----------------|-----------|-------|
| **POST** `/{slug}/appointments/public/{id}/cancel` | `public.py:1080` | `AppointmentCancelResponse` | ✅ Да | `cancel_appointment` → `get_appointment_snapshot` |
| **PATCH** `/{slug}/appointments/public/cancel` | `public.py:941` | `AppointmentRead` | ❌ Нет | Ручной refresh entity, не snapshot |

**Проблема:** PATCH cancel возвращает `AppointmentRead` (entity-style), без snapshot и без `can_reschedule`/`can_cancel`.

### Вывод
- **POST** cancel — уже возвращает fresh snapshot.
- **PATCH** cancel — нарушает контракт. Нужно привести к `AppointmentCancelResponse` и делегировать в `_cancel_public_appointment`.

**Итого:** public cancel returns fresh snapshot — частично (POST ✅, PATCH ❌).

---

## Шаг 2. Public reschedule → fresh snapshot response

### Текущее состояние
- **Файл:** `backend/app/api/endpoints/public.py` (строки 1001–1074)
- **Response:** `AppointmentRescheduleResponse` с `snapshot: AppointmentSnapshotResponse`
- **Источник snapshot:** `reschedule_appointment` → `get_appointment_snapshot` после commit

**Итого:** public reschedule returns fresh snapshot ✅

---

## Шаг 3. Unified self-service action response contract

### Текущие контракты
- `AppointmentCancelResponse`: `appointment_id`, `tenant_id`, `status`, `cancelled`, `snapshot`
- `AppointmentRescheduleResponse`: `appointment_id`, `tenant_id`, `rescheduled`, `old_start_time`, `old_end_time`, `new_start_time`, `new_end_time`, `status`, `snapshot`

### Общее
- Оба содержат `snapshot: AppointmentSnapshotResponse` с `can_reschedule`, `can_cancel`.
- Различие только в action-specific полях (`cancelled` vs `rescheduled`, `old_*` / `new_*`).

**Вывод:** Контракт уже унифицирован по snapshot. Нужно только убрать PATCH cancel (или перевести на этот же контракт).

---

## Шаг 4. Service-driven orchestration

### cancel
- **Service:** `appointment_lifecycle_service.cancel_appointment`
- Access-check: в роуте (`_require_public_appointment_access`) и в service (tenant scope).
- Endpoint вызывает service → получает snapshot → возвращает response.

### reschedule
- **Service:** `appointment_lifecycle_service.reschedule_appointment`
- Access-check в роуте, lifecycle и snapshot в service.

**Вывод:** orchestration уже в service, endpoints в целом тонкие. PATCH cancel содержит лишний stmt_refresh и не использует единый snapshot-путь.

---

## Шаг 5. Capability flags refresh

- `AppointmentSnapshotResponse` содержит `can_reschedule`, `can_cancel`.
- Считаются в `appointment_snapshot_service._build_snapshot_from_appt` через `can_reschedule_appointment()` и `can_cancel_appointment()` из `appointment_lifecycle_rules`.
- CANCELLED → `can_cancel=False`, `can_reschedule=False`.

**Итого:** action responses return refreshed capability flags ✅

---

## Шаг 6. Idempotency для public cancel

- `appointment_lifecycle_service.cancel_appointment`: если `status == CANCELLED`, возвращает текущий snapshot, `transitioned=False`.
- Нет дублирования history.
- `test_public_cancel_already_cancelled_is_idempotent` покрывает.

**Итого:** public cancel idempotent ✅

---

## Шаг 7. Concurrency / race для reschedule

- `RescheduleSlotConflictError` → HTTP 409 "Выбранное время уже занято"
- `RescheduleForbiddenError` → 422 "Недопустимый статус"
- Service после commit ловит `IntegrityError` и re-raise `RescheduleSlotConflictError`
- Обработка в `public.py:1039–1049`

**Итого:** public reschedule race handling fixed ✅

---

## Шаг 8. Regression tests

### Уже есть (test_public_workflow.py)
- `test_public_cancel_success_returns_snapshot_and_creates_history`
- `test_public_cancel_access_denied_for_foreign_appointment`
- `test_public_cancel_appointment_not_found_returns_404`
- `test_public_cancel_forbidden_status_returns_422`
- `test_public_cancel_already_cancelled_is_idempotent_and_does_not_duplicate_history`
- `test_public_reschedule_success_creates_history_and_returns_snapshot`
- `test_public_reschedule_access_denied_for_foreign_appointment`
- `test_public_reschedule_slot_conflict_returns_409`
- и др.

### Чего может не хватать
- Явной проверки `can_reschedule`/`can_cancel` в ответах cancel/reschedule.
- Теста на PATCH cancel (если оставляем), чтобы он возвращал snapshot-style response.

---

## План действий ✅ Выполнено

1. PATCH cancel переведён на `AppointmentCancelResponse` и делегирует в `_cancel_public_appointment`.
2. PATCH cancel возвращает fresh snapshot.
3. Добавлены regression-тесты: `test_public_cancel_returns_fresh_snapshot_with_capability_flags`, `test_public_reschedule_returns_fresh_snapshot_with_capability_flags`, `test_public_patch_cancel_returns_fresh_snapshot`.

---

## Итог по контуру (Checklist)

| # | Критерий | Статус |
|---|----------|--------|
| 1 | public cancel returns fresh snapshot | ✅ POST + PATCH |
| 2 | public reschedule returns fresh snapshot | ✅ |
| 3 | action responses unified (snapshot-based) | ✅ |
| 4 | endpoints thin, service-driven | ✅ |
| 5 | capability flags refreshed after action | ✅ |
| 6 | cancel idempotent | ✅ |
| 7 | reschedule race handling | ✅ 409/422 |
| 8 | regression tests | ✅ |
