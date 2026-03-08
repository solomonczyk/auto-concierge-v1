# SaaS Operational Gaps — Gap Analysis

Анализ узких мест перед выходом на рынок. Архитектура сильная — фокус на операциях, интеграциях, наблюдаемости, onboarding.

---

## 1. Operator Layer (операционная работа)

### 1.1 Audit Log

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| `appointment_status_changed` | ✅ `AppointmentHistory` — old_status, new_status, changed_by_user_id, source, created_at | — |
| `appointment_created` | ✅ Запись в AppointmentHistory при создании | — |
| `client_updated` | ❌ Нет | Нужна таблица `audit_log` или расширение |
| `user_login` | ⚠️ Логируется в login.py (request_id, user_id, tenant_id) | Нет персистентного хранения |
| `settings_changed` | ❌ Нет | — |

**Рекомендация:** Универсальная таблица `audit_log` (event_type, entity_type, entity_id, tenant_id, user_id, payload, created_at) + middleware/decorator для записи.

### 1.2 Soft Delete

| Сущность | Текущее состояние | Gap |
|---------|------------------|-----|
| Clients | ❌ Hard delete (нет DELETE endpoint, но модель без deleted_at) | Нужен deleted_at |
| Appointments | ❌ Hard delete (`DELETE /{id}` удаляет запись и history) | Критично |
| Users | ❌ is_active, но нет deleted_at | — |
| Services | ❌ Hard delete | — |

**Рекомендация:** Добавить `deleted_at` (nullable datetime) в Client, Appointment, User, Service. Все SELECT фильтровать `WHERE deleted_at IS NULL`. Удаление = `UPDATE SET deleted_at = now()`.

### 1.3 Защита статусов

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| status_change_reason | ❌ Нет в AppointmentHistory | Добавить колонку |
| status_changed_by | ✅ changed_by_user_id | — |
| status_changed_at | ✅ created_at | — |

**Рекомендация:** Добавить `reason: Optional[str]` в AppointmentHistory и в PATCH schema.

---

## 2. Интеграции

### 2.1 Fail-safe

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| commit → then integrate | ✅ `create_appointment`: commit → enqueue_appointment | — |
| Integration не ломает flow | ✅ enqueue в try/except, ошибка только логируется | — |

**Статус:** ✅ Реализовано корректно.

### 2.2 Retry Queue

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| status, attempt_count, next_retry_at | ⚠️ RQ retry=3, но нет персистентной таблицы | Нет видимости для оператора |
| Webhook retry | ❌ Webhook — синхронный, без очереди | — |

**Рекомендация:** Таблица `integration_jobs` (entity_type, entity_id, status, attempt_count, next_retry_at, last_error). RQ failed jobs → перенос в эту таблицу.

### 2.3 Dead Letter Queue

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| status=failed после N попыток | ❌ RQ failed jobs не видны оператору | — |
| UI для оператора | ❌ Нет | — |

**Рекомендация:** Dashboard-раздел «Неудачные интеграции» с возможностью retry вручную.

---

## 3. Наблюдаемость

### 3.1 Error Tracking

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| Sentry / аналог | ❌ Нет | Критично для prod |
| traceback, tenant_id, endpoint, payload | ⚠️ Логируется в global_exception_handler | Нет агрегации |

**Рекомендация:** Интеграция Sentry (sentry-sdk). DSN в .env. Автоматический capture исключений с context (tenant_id, request_id, user_id).

### 3.2 Алерты

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| 500 spike | ⚠️ Prometheus HTTP_ERROR_TOTAL | Нет alerting rules |
| DB pool exhaustion | ❌ Нет метрик | — |
| Redis failure | ⚠️ /ready проверяет Redis | Нет алерта |
| Worker crash | ❌ Нет | — |

**Рекомендация:** Prometheus Alertmanager + правила. Или Sentry performance/alerts.

### 3.3 Request Correlation

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| request_id | ✅ Middleware, X-Request-ID в response | — |
| tenant_id в логах | ✅ log_requests middleware | — |

**Статус:** ✅ Реализовано.

---

## 4. Tenant Lifecycle

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| active | ✅ TenantStatus.ACTIVE | — |
| trial | ❌ Нет | Добавить в enum |
| suspended | ✅ TenantStatus.SUSPENDED | — |
| deleted | ❌ Нет | Добавить + soft delete tenant |
| Блокировка доступа | ⚠️ Частично (проверки по status) | Нужна middleware для suspended/deleted |

**Рекомендация:** Расширить TenantStatus: TRIAL, DELETED. Middleware: при suspended/deleted → 403 для всех API кроме superadmin.

---

## 5. Rate Limiting

| Endpoint | Текущее состояние | Gap |
|----------|------------------|-----|
| login | ✅ 10/min | — |
| public (services, slots, appointments) | ✅ 30–60/min | — |
| webhook | ✅ 120/min | — |
| ws_ticket | ✅ 30/min | — |

**Статус:** ✅ Покрыто slowapi.

---

## 6. Резервное восстановление

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| Backup | ✅ pg_dump, скрипты | — |
| Recovery test | ❌ Не документирован | Критично |
| Restore в отдельный контейнер | ❌ Не проверено | — |

**Рекомендация:** Один раз выполнить: restore backup → новый postgres контейнер → поднять API → smoke test. Зафиксировать в RUNBOOK.

---

## 7. Onboarding клиента

| Требование | Текущее состояние | Gap |
|------------|------------------|-----|
| default working hours | ✅ TenantSettings: work_start=9, work_end=18, slot_duration=30 | — |
| default services | ✅ seed_services при создании tenant | — |
| demo data | ⚠️ create_demo_tenant, demo endpoint | Нет «первого входа» wizard |

**Рекомендация:** При первом логине (tenant без appointments) — показать краткий onboarding или подсказки. Опционально: кнопка «Загрузить демо-данные».

---

## Приоритизация

| Приоритет | Область | Действие | Оценка |
|-----------|---------|----------|--------|
| P0 | Operator | Soft delete (appointments, clients) | 2–3 дня |
| P0 | Observability | Sentry интеграция | 0.5 дня |
| P1 | Operator | status_change_reason в AppointmentHistory | 0.5 дня |
| P1 | Operator | Универсальный audit_log (client_updated, login, settings) | 1–2 дня |
| P1 | Tenant | TenantStatus: trial, deleted + middleware | 1 день |
| P2 | Integrations | integration_jobs + DLQ UI | 2–3 дня |
| P2 | Recovery | Recovery test в RUNBOOK | 0.5 дня |
| P3 | Onboarding | First-login hints / demo button | 1 день |

---

## Ссылки

- `backend/app/models/models.py` — AppointmentHistory, TenantStatus
- `backend/app/main.py` — request_id, logging
- `backend/app/services/external_integration_service.py` — fail-safe pattern
- `docs/BACKUP_RESTORE.md`, `docs/RUNBOOK.md`
