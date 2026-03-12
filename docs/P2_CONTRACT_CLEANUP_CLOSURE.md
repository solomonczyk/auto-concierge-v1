# P2 Contract Cleanup — Closure

## What was done

- **public read/write** — migrated to `auto_info` (response and request schemas)
- **internal update contract** — `AppointmentUpdate` and mutation flow use `auto_info`
- **frontend types/components** — `Appointment`, `UpdateAppointmentData`, `BookingPage`, `KanbanBoard`, `AppointmentEditDialog` use `auto_info`
- **PUT fallback path** — when `integration_appt` is used without `auto_snapshot`, the handler now loads it explicitly before `_enrich`

## Status

**migration/contract contour closed**
