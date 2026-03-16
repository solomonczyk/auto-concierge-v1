# Booking Lifecycle – Final Acceptance

Source of truth:

- APPOINTMENT_LIFECYCLE.md
- PROJECT_EXECUTION_STRATEGY.md
- USER_SCENARIOS_FULL_SET.md
- CONTROLLED_STO_LAUNCH_PLAN.md

Goal:

Verify that the full booking lifecycle works reliably end-to-end.

---

## Acceptance Checklist

| # | Acceptance condition | Source | Automated test | Manual check | Status |
|---|---|---|---|---|---|
| 1 | Client can create appointment | APPOINTMENT_CORE_DEFINITION | TBD | create booking via public API | planned |
| 2 | Appointment belongs to correct tenant | TENANT_ISOLATION_FINAL_ACCEPTANCE | covered | create A/B tenants | done |
| 3 | Appointment visible to operator dashboard | USER_SCENARIOS | TBD | operator opens appointment | planned |
| 4 | Status lifecycle works (new → confirmed → completed) | APPOINTMENT_LIFECYCLE | TBD | change status via API | planned |
| 5 | DB prevents double booking (slot overlap) per tenant+service | DB constraint (appointments_no_overlap) | TBD | N/A (DB-level) | done |
| 6 | Cancelled appointments do not trigger reminders | APPOINTMENT_LIFECYCLE | TBD | cancel and wait reminder window | planned |
| 7 | Reminder delivery works | CONTROLLED_STO_LAUNCH_PLAN | TBD | wait reminder window | planned |
| 8 | WebSocket updates propagate appointment changes | WS_EVENT_CONTRACT | TBD | observe operator UI | planned |
| 9 | Telegram notification sent via tenant bot | notification_service | covered | check message delivery | planned |

---

## Exit condition

Booking lifecycle verified across:

- API layer
- worker / reminder pipeline
- notification layer
- operator dashboard

Result: **booking lifecycle stable**

## Technical verification (2026-03)

Double booking / race condition protection:
- Added DB constraint: appointments_no_overlap (EXCLUDE USING gist on tenant_id, service_id, tstzrange(start_time,end_time,'[)') WITH &&) WHERE deleted_at IS NULL
- Migration: 998c7b53488c_p0_prevent_double_booking_with_gist_.py
Result: overlapping bookings are rejected at DB level (race-safe).


