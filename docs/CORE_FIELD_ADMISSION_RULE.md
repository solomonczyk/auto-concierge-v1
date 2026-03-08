# Core Field Admission Rule

## Purpose

This document defines when a new field is allowed to be added to a core platform entity.

## Rule

A new field may be added to a core entity only if **all** conditions are true:

1. The field makes sense across all current and future verticals
2. The field describes a platform-level concept, not an industry-specific detail
3. The field is required for the core workflow / booking / tenant / audit / integration model
4. The field would still be valid if **Auto Service vertical did not exist**

If any condition is false, the field must not be added to core.

## Examples Allowed in Core

- `tenant_id`
- `client_id`
- `status`
- `start_at`
- `end_at`
- `notes` (generic)
- `integration_status`
- `created_at`
- `updated_at`

## Examples Rejected from Core

- `vin`
- `car_make`
- `car_year`
- `mechanic_id`
- `doctor_id`
- `stylist_id`
- `diagnosis`
- `repair_type`
- `course_id`

## Default Decision

When in doubt, **reject** the field from core and place it in a vertical extension model.
