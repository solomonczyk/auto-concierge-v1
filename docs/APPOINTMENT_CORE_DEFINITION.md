# Appointment Core Definition

## Definition

Appointment is a core platform entity that represents a **scheduled booking / reservation / workflow instance** between a client and a business process.

## Core Meaning

Appointment must stay industry-neutral.

It may represent:

- service booking
- consultation booking
- repair visit
- lesson/session
- resource reservation
- field service visit

## Core Responsibilities

Appointment in core may contain only platform-neutral concepts:

- `tenant_id`
- `client_id`
- `resource_id` (future)
- slot / `start_at` / `end_at`
- `status`
- `notes` (generic)
- `created_at` / `updated_at`
- workflow linkage
- integration linkage
- audit linkage

## Must Not Live in Core

Examples of vertical-only data:

| Vertical | Must not live in core |
|----------|------------------------|
| Auto Service | VIN, car make / model / year, repair category |
| Clinic | diagnosis, medical notes, doctor specialty |
| Beauty | stylist specialization, beauty procedure specifics |
| Education | course metadata, group / lesson-specific attributes |

## Rule

If data describes the industry-specific context of the booking, it belongs to a vertical extension, not to Appointment core.
