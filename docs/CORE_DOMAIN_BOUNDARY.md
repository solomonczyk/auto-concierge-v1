# Core Domain Boundary

## Core Domain (platform)

These entities belong to platform core and must stay industry-neutral:

- Tenant
- User
- Client
- Appointment
- Resource (future)
- Slot
- Workflow State
- Notification
- Audit Log
- Outbox Event

## Vertical Domain

Vertical data must never be stored in core entities.

**Examples:**

| Vertical | Vertical-only concepts |
|----------|------------------------|
| Auto Service | vehicle information, VIN, car model, repair type |
| Clinic | medical record, doctor specialization, diagnosis |
| Beauty | service category, stylist specialization |
| Field Service | visit address, route, crew assignment |
| Resource Booking | resource type, capacity, buffer rules |
| Education | course, group, curriculum |

## Architectural Rule

Core entities must represent concepts that exist in **all verticals**.

If a field only makes sense in one industry, it must go to a vertical extension table.
