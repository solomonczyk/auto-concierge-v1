# Risk: Single Resource Scheduling Per Shop

## Status
Open. Accepted launch limitation.

## Severity
P1 domain limitation

## Current behavior
Appointments are protected from overlap by the database constraint:

`appointments_no_overlap_per_shop`

The constraint is defined on:

- `shop_id`
- `tstzrange(start_time, end_time, '[)')`

Active statuses included:

- `NEW`
- `CONFIRMED`
- `IN_PROGRESS`

## Confirmed schema reality
The `appointments` table currently has no dedicated planning resource field such as:

- `resource_id`
- `bay_id`
- `operator_id`
- `capacity`
- `slot_capacity`

Therefore the current effective scheduling model is:

**one schedulable resource per shop**

## Why current behavior is valid
For the current launch baseline, this behavior is internally consistent:
one appointment occupying a time slot blocks the whole shop.

This prevents double booking under the existing STO launch model.

## Why this becomes a future risk
This model will produce false conflicts if the product evolves to support:

- multiple service bays
- multiple operators working in parallel
- parallel capacity within one shop
- resource-specific calendars
- partial slot allocation

## Architectural conclusion
Current constraint is accepted as a **launch-safe baseline**.

It must be redesigned when resource-based scheduling is introduced.

## Recommended future migration target
Replace overlap protection from:

- `shop_id + time range`

to one of:

- `resource_id + time range`
- `shop_id + bay_id + time range`
- `shop_id + operator_id + time range`

depending on the final scheduling domain model.

## Trigger for redesign
Redesign becomes mandatory immediately when any of the following appears in scope:

- service bay scheduling
- operator scheduling
- parallel bookings in one shop
- capacity-based slot allocation

