# Known Technical Debt — Auto-Concierge

Items here are **pre-existing** and **not caused by recent auth/security migration**.
They should not block rollout but need to be resolved eventually.

## Test Failures (pre-existing, unrelated to auth migration)

| Test | File | Reason | Impact |
|---|---|---|---|
| `test_services_public_returns_public_tenant_services` | `test_public_workflow.py` | Endpoint returns 410 (deprecated) | None — endpoint intentionally removed |
| `test_read_services` | `test_services.py` | Requires auth, uses old auth flow | Low — covered by `test_services_api.py` |

## Code Quality

| Item | Location | Notes |
|---|---|---|
| `pydantic V1 Config` class usage | `appointments.py` models | Should migrate to `model_config = ConfigDict(...)` |
| `datetime.utcnow()` deprecation | `python-jose` dependency | Third-party lib issue, watch for updates |
| Duplicate `from pydantic import BaseModel` | `appointments.py:80` | Minor import duplication |
| RuntimeWarning: unawaited coroutine | `test_create_appointment_authorized` | Mock setup issue, no runtime impact |

## Architecture

| Item | Notes |
|---|---|
| `_sync_to_1c` / `_sync_to_alpha_auto` are stubs | Real integration pending first client |
| Notification fire-and-forget via `asyncio.create_task` | No retry, no dead letter queue |
| Public booking collision lock cleanup | `redis.delete(lock_key)` only for new bookings |
