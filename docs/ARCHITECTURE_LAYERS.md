# Architecture Layers

Карта текущего backend по трём слоям (по `backend/app/`).

---

## Platform Layer
(универсальная логика: tenant, auth, clients, appointments core, workflow, audit, integration framework)

| Module | Path |
|--------|------|
| Tenant system | `core/tenant_resolver.py` |
| Auth | `core/security.py` |
| Auth API | `api/endpoints/login.py` |
| Clients API | `api/endpoints/clients.py` |
| Appointments core API | `api/endpoints/appointments.py` |
| Slots / Resource Calendar | `core/slots.py`, `api/endpoints/slots.py` |
| Services catalog | `api/endpoints/services.py` |
| Shops / Locations | `api/endpoints/shops.py` |
| Tenants API | `api/endpoints/tenants.py` |
| Public booking | `api/endpoints/public.py` |
| Workflow / State machine | `services/appointment_state_machine.py` |
| SLA timers (confirm, no-show) | `services/sla_service.py` |
| SLA API | `api/endpoints/sla.py` |
| Notification system | `services/notification_service.py`, `services/reminder_service.py` |
| Audit | `services/audit_service.py`, `api/endpoints/admin.py`, `schemas/audit_log.py`, `schemas/deleted_record.py` |
| Integration framework | `services/external_integration_service.py`, `services/appointment_integration_service.py` |
| Appointment history | `schemas/appointment_history.py` |
| Features | `api/endpoints/features.py` |
| Plan limits / Usage | `services/plan_limits.py`, `services/usage_service.py` |
| Analytics | `services/analytics_service.py` |
| Models (platform entities) | `models/models.py` |
| API deps | `api/deps.py` |
| Bot tenant resolver | `bot/tenant.py` |

---

## Vertical Layer (Auto Service)
(логика СТО: car_*, repair lifecycle, Telegram-бот, AI-диагностика)

| Module | Path |
|--------|------|
| Telegram bot handlers | `bot/handlers.py` |
| Bot loader | `bot/loader.py` |
| Bot messages | `bot/messages.py` |
| Bot keyboards | `bot/keyboards.py` |
| Bot states | `bot/states.py` |
| Telegram webhook | `api/endpoints/webhook.py` |
| AI diagnostics (СТО) | `services/ai_service.py`, `services/ai_core.py` |
| Voice service | `services/voice_service.py` |
| Demo workflow | `services/demo_workflow.py` |
| Vertical fields in models | `models/models.py` (Client.car_make, car_year, vin; Appointment.car_make, car_year, vin) |

---

## Infrastructure Layer
(техническая инфраструктура: DB, Redis, WS, workers, monitoring)

| Module | Path |
|--------|------|
| Database | `db/session.py` |
| Redis | `services/redis_service.py` |
| WebSocket | `api/endpoints/ws.py`, `api/endpoints/ws_ticket.py` |
| WS auth | `services/ws_ticket_service.py`, `services/ws_ticket_store.py`, `services/ws_auth_resolver.py`, `models/ws_auth_context.py` |
| Outbox (reliability) | `services/outbox_service.py`, `services/outbox_dispatcher.py` |
| Background workers | `worker.py` |
| Config | `core/config.py` |
| Logging | `core/logging_config.py` |
| CSRF | `core/csrf.py` |
| Rate limiting | `core/rate_limit.py` |
| Metrics / Monitoring | `core/metrics.py` |
| Request context | `core/context.py` |
| App bootstrap | `main.py` |
| API router | `api/api.py` |
| Sentry test | `api/endpoints/_sentry_test.py` |
| Demo (dev) | `api/endpoints/demo.py` |
| Bot client (aiogram) | `bot/client.py` |

---

## Platform Leaks (Auto Service in Core)

Места, где СТО-специфика попала в platform-слой.

| File | Leak | Reason | Destination |
|------|------|--------|-------------|
| `backend/app/models/models.py` | `Client`: `car_make`, `car_year`, `vin` | Auto-specific data in shared Client model | Vertical Layer (extension table / mixin) |
| `backend/app/models/models.py` | `Appointment`: `car_make`, `car_year`, `vin` | Auto-specific data in shared Appointment model | Vertical Layer (extension table / mixin) |
| `backend/app/api/endpoints/clients.py` | `ClientOut.vehicle_info`, `ClientCarInfo` schema, enrichment loop `car_make`+`car_year`+`vin` → `vehicle_info` | Vehicle/car concepts are STO-only | Vertical Layer |
| `backend/app/api/endpoints/appointments.py` | Schemas: `ApptUpdate`, `ApptCreate`, `AppointmentPublicPayload` — `car_make`, `car_year`, `vin`; update logic for these fields | Car/vehicle info at booking is STO-specific | Vertical Layer |
| `backend/app/api/endpoints/public.py` | Schemas and payloads: `car_make`, `car_year`, `vin`; endpoint `GET /clients/public` → `ClientCarInfo` (car-centric, 404 "no car data") | Public booking assumes vehicle; endpoint is car-only | Vertical Layer |
| `backend/app/schemas/deleted_record.py` | `DeletedAppointmentPayload`: `car_make`, `car_year`, `vin` | Mirrors model; STO-specific fields in platform schema | Vertical Layer (or future extension module) |
| `backend/app/services/notification_service.py` | `status_messages`: `"in_progress"` → «Мастер приступил к работе над вашим автомобилем», `"completed"` → «Ваш автомобиль готов!» | Hardcoded STO wording (мастер, автомобиль) | Vertical Layer — notification templates configurable per vertical |
| `backend/app/services/analytics_service.py` | `bookings_by_category`: `"maintenance"`, `"repairs"` | Repair terminology, STO-centric metrics | Vertical Layer or future extension (analytics dimensions per vertical) |

---

## Leak Migration Priority

### P1 — move first

| File | Leak | Reason |
|------|------|--------|
| `backend/app/models/models.py` | `Client`: `car_make`, `car_year`, `vin` | Blocks platform purity; shared core model; every vertical would inherit these columns |
| `backend/app/models/models.py` | `Appointment`: `car_make`, `car_year`, `vin` | Same — core appointment model; affects many endpoints and schemas |

**Reason:** Core models are the foundation. Moving car_* into extension tables / mixin enables clean vertical layering.

### P2 — move after core cleanup

| File | Leak | Reason |
|------|------|--------|
| `backend/app/api/endpoints/clients.py` | `ClientOut.vehicle_info`, `ClientCarInfo`, enrichment loop | API-level STO specificity; depends on P1 |
| `backend/app/api/endpoints/appointments.py` | Schemas and update logic for `car_make`, `car_year`, `vin` | API-level; follows model structure |
| `backend/app/api/endpoints/public.py` | Payloads, `GET /clients/public` → `ClientCarInfo` | Public booking flow; depends on P1 |
| `backend/app/schemas/deleted_record.py` | `DeletedAppointmentPayload`: `car_make`, `car_year`, `vin` | Mirrors model; trivial once P1 done |

**Reason:** API and schema changes follow model cleanup. Not destructive to core, but touch many call sites.

### P3 — move later

| File | Leak | Reason |
|------|------|--------|
| `backend/app/services/notification_service.py` | Hardcoded messages: «Мастер приступил…», «Ваш автомобиль готов!» | Presentation / wording; no impact on data model |
| `backend/app/services/analytics_service.py` | `bookings_by_category`: `"maintenance"`, `"repairs"` | Analytics dimensions; cosmetic, configurable later |

**Reason:** Wording and analytics; can be parameterized per vertical without structural refactor.
