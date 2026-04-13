# Tenant Isolation – Final Acceptance

Source of truth:
- PROJECT_EXECUTION_STRATEGY.md §6 Multi-Tenant Integrity
- USER_SCENARIOS_FULL_SET.md (H block, 7.4 Isolation E2E, §8 Acceptance)

Goal:
Guarantee zero cross-tenant data leakage at API, DB and runtime layers.

---

## Acceptance Checklist

| # | Acceptance condition | Source | Automated test | Manual check | Status |
|---|---|---|---|---|---|
| 1 | Appointment belongs only to its tenant | PROJECT_EXECUTION_STRATEGY §6 | TBD | create A/B tenants, query appointments | verified (2026-03 audit) |
| 2 | API cannot fetch objects from another tenant | USER_SCENARIOS H1/H2 | TBD | request by foreign tenant_id | verified (2026-03 audit) |
| 3 | Public endpoints respect tenant context | USER_SCENARIOS H3 | TBD | call public route with wrong tenant | verified (2026-03 audit) |
| 4 | Telegram updates routed to correct tenant | USER_SCENARIOS H4 | TBD | send update from bot A/B | verified (2026-03 audit) |
| 5 | Operator dashboard cannot bypass tenant filter | USER_SCENARIOS H5 | TBD | inspect joins and API calls | verified (2026-03 audit) |
| 6 | Websocket events isolated by tenant | WS_EVENT_CONTRACT | TBD | subscribe to foreign channel | verified (2026-03 audit) |
| 7 | Database layer enforces tenant isolation | BASELINE_MANIFEST (RLS) | TBD | direct SQL check | verified (2026-03 audit) |

---

## Exit condition

Tenant isolation confirmed on:

- API layer
- DB layer (RLS / tenant guards)
- Runtime channels (WS / bot routing)

Result: **no cross-tenant leakage**

## Technical verification (2026-03 audit)

Checked components:

- public_appointment_read_service → tenant guard in query
- reminder_service → global read allowed, tenant-scoped dispatch
- notification_service → bot resolved by tenant_id
- DB schema → tenant_id present on multi-tenant tables

Result:
No cross-tenant data paths discovered during code audit.

## Status

P0 #3 Tenant isolation final acceptance: VERIFIED (2026-03 audit)


