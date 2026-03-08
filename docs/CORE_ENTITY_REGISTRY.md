# Core Entity Registry

## Core Entities

These entities belong to platform core and must remain industry-neutral.

- Tenant
- User
- Client
- Appointment
- Resource (future)
- Slot (future)
- WorkflowState
- Notification
- AuditLog
- OutboxEvent

## Rule

No new entity can be added to core unless it satisfies:

1. Exists in **all** verticals
2. Represents a platform-level concept
3. Not tied to any specific industry

Otherwise it must be implemented as a vertical module.
