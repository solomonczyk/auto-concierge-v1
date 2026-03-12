# Appointment Lifecycle Actions Layer

**Cancel is the canonical lifecycle action.** All future flows (Telegram WebApp, operator dashboard, reminders, self-service) must use this endpoint and service — do not scatter cancel logic elsewhere.

## Endpoint

- `POST /api/v1/appointments/{appointment_id}/cancel`

## Response Contract

```json
{
  "appointment_id": 123,
  "tenant_id": 1,
  "status": "CANCELLED",
  "cancelled": true,
  "snapshot": { ... }
}
```

Returns `AppointmentSnapshotResponse` inside `snapshot`. The endpoint reuses `get_appointment_snapshot()` — it does not assemble data manually.

## Cancel Rules

| Rule | Description |
|------|-------------|
| Forbidden | Cannot cancel `COMPLETED` or `NO_SHOW` |
| Idempotent | If already `CANCELLED` → return current snapshot (200) |
| History | On transition, record `CANCELLED` in `AppointmentHistory` |

## Access Control

- Allowed: `SUPERADMIN`, `ADMIN`, `MANAGER`, `STAFF`
- Not yet: Telegram WebApp, public API, self-service

## Tenant Isolation

- Cross-tenant → 404 (do not reveal existence)

## Reminder Compatibility

- `REMIND_STATUSES = {NEW, CONFIRMED}` — `CANCELLED` excluded
- Cancelled appointments do not receive reminders
