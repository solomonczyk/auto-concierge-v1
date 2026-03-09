# External Integration Test Alignment — Closure

## Summary

The **direct-sync HTTP contract** has been removed from the test suite. All HTTP mutation flows are now aligned with the transactional outbox pattern.

## Changes

### HTTP mutation flows no longer assert immediate integration success/failure

- Tests no longer expect `integration_status == "failed"` or `integration_status == "success"` in the HTTP response immediately after `POST`, `PUT`, or `PATCH`.
- Integration runs asynchronously via the outbox worker; the API layer only enqueues events and returns business data.

### Create / PUT / PATCH tests now assert business success + outbox event creation

| Flow       | Business assertion                        | Outbox assertion                    |
|------------|-------------------------------------------|-------------------------------------|
| POST create| HTTP 200, `integration_status == "pending"`| `OutboxEvent` with `appointment_created` |
| PUT        | HTTP 200, payload and DB data updated      | `OutboxEvent` with `appointment_updated`  |
| PATCH status| HTTP 200, status updated in DB            | `OutboxEvent` with `appointment_updated`  |

### Worker / service-level integration state is tested separately

- `test_failed_integration_is_cleared_after_successful_retry` calls `run_appointment_integration_sync` directly (as the outbox worker does) and asserts `IntegrationStatus.SUCCESS` after a successful retry.
- Integration success/failure semantics are tested at the service layer, not in HTTP mutation tests.

## Files

- `backend/tests/test_external_integration_fail_safe.py` — all tests aligned with the outbox contract.
