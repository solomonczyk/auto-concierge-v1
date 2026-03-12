# Appointment Snapshot — Core Read-Model

**Canonical source of truth for reading appointment data.**

New UI/flows must use `GET /api/v1/appointments/{appointment_id}/snapshot` instead of assembling "own version" of the record from different endpoints.

## Contract (frozen)

- `appointment_id`, `tenant_id`, `status`, `start_time`, `end_time`
- `client`: `{id, name, phone}` (nullable)
- `service`: `{id, name}` (nullable)
- `shop`: `{id, name}` (nullable)
- `intake`: `{status}` (nullable)
- `source`: WEBAPP | DASHBOARD | API | BOT | SYSTEM
- `is_waitlist`: boolean

## Snapshot Reuse Map

| Consumer | Status | Notes |
|----------|--------|-------|
| Operator appointment detail | Can migrate | Replace GET /appointments/{id} with snapshot for read-only views |
| Reminder payload building | Can migrate | Use snapshot in reminder_service instead of ad-hoc fetch |
| Booking success / confirmation screen | Can migrate | Public flow returns AppointmentRead; snapshot suitable for internal use |
| Reschedule / cancel flows | Planned | Use snapshot as input to reschedule/cancel logic |
| Support / debug views | Can migrate | Single read-model for support tooling |

**Что оставить как есть сейчас:**  
- `GET /appointments/{id}` — сохранён для backward compatibility, Kanban и редактирования  
- Public flow — пока без изменений, WebApp использует свои endpoint'ы

## Access

- Superadmin, tenant admin, operator — allowed (via `get_current_tenant_id`)
- Unauthenticated — 401
- Cross-tenant — 404

## Files

- `backend/app/schemas/appointment_snapshot.py` — Pydantic schemas
- `backend/app/services/appointment_snapshot_service.py` — read-model service
- `backend/app/api/endpoints/appointments.py` — GET `/{id}/snapshot`
