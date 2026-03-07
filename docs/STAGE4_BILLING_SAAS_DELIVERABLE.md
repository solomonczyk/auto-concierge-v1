# Stage 4: Billing / SaaS Readiness — Deliverable

## Пути к файлам

### Модели / миграции
- `backend/app/models/models.py` — TariffPlan, Tenant (tariff_plan_id)
- `backend/alembic/versions/a1b2c3d4e5f6_add_saas_plans_starter_business_enterprise.py` — миграция планов

### Сервисы limit/usage
- `backend/app/services/plan_limits.py` — конфиг лимитов по плану
- `backend/app/services/usage_service.py` — usage counters, enforcement, feature gating

### Изменённые endpoints
- `backend/app/api/endpoints/appointments.py` — create_appointment: проверка лимита appointments
- `backend/app/api/endpoints/public.py` — create_public_appointment: проверка лимита (только для новых записей)
- `backend/app/api/endpoints/features.py` — GET /features, GET /features/analytics/advanced (enterprise-only)

### Тесты
- `backend/tests/test_billing_saas.py`

---

## Планы

| Plan       | max_users | max_appointments_per_month | max_webhook_per_day | max_ai_per_day |
|------------|-----------|---------------------------|---------------------|----------------|
| starter    | 3         | 50                        | 100                 | 0              |
| business   | 15        | 500                       | 2000                | 100            |
| enterprise | 100       | 5000                      | 20000               | 1000           |

Legacy alias: free→starter, standard→business, pro→enterprise.

---

## Лимиты (config layer)

Лимиты заданы в `plan_limits.py`, без отдельной таблицы в БД.

---

## Имена тестов

- `test_get_limits_starter` — лимиты starter
- `test_get_limits_business` — лимиты business
- `test_get_limits_enterprise` — лимиты enterprise
- `test_get_limits_legacy_alias` — free/standard/pro → starter/business/enterprise
- `test_get_limits_none_defaults_to_starter` — None → starter
- `test_feature_webhook_starter_denied` — webhook denied для starter
- `test_feature_webhook_business_allowed` — webhook allowed для business+
- `test_feature_advanced_analytics_enterprise_only` — advanced_analytics только enterprise
- `test_get_features_for_plan_starter` — флаги для starter
- `test_get_features_for_plan_enterprise` — флаги для enterprise
- `test_get_appointments_this_month_counts_correctly` — usage counter
- `test_check_appointments_limit_raises_when_exceeded` — LimitExceededError при превышении
- `test_create_appointment_within_limit_succeeds` — tenant в лимите → успех
- `test_create_appointment_exceeds_limit_returns_403_structured` — превышение → 403 + structured detail
- `test_features_endpoint_returns_plan_based_flags` — GET /features по плану
- `test_advanced_analytics_returns_403_for_starter` — 403 для starter
- `test_advanced_analytics_returns_200_for_enterprise` — 200 для enterprise
- `test_tenant_plan_correctly_read` — plan читается из tenant

---

## Assert'ы

- **Usage increment**: `test_get_appointments_this_month_counts_correctly` — создаём 3 appointment, assert count >= 3
- **Reject при превышении**: `test_create_appointment_exceeds_limit_returns_403_structured` — заполняем до лимита, 51-й → 403, detail содержит code, limit_name, current, limit
- **Feature gate**: `test_advanced_analytics_returns_403_for_starter`, `test_advanced_analytics_returns_200_for_enterprise`

---

## Пример payload ошибки при превышении лимита

```json
{
  "detail": {
    "code": "limit_exceeded",
    "limit_name": "max_appointments_per_month",
    "current": 50,
    "limit": 50,
    "message": "Limit exceeded: max_appointments_per_month (current=50, limit=50)"
  }
}
```

HTTP status: **403 Forbidden**
