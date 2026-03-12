# Reminder Runtime — Closure

## What was fixed
- tenant-aware reminder timezone support added
- reminder worker added to FastAPI lifespan
- duplicate reminder runtime removed from `app.worker`
- soft-deleted appointments excluded from reminders
- batch tenant timezone lookup added
- reminder feature flag added: `ENABLE_REMINDER_WORKER`

## Tests
- `backend/tests/test_reminder_service.py` → 3 passed
- regression slice: `pytest -q -k "reminder or appointments or public_workflow"` → 75 passed, 1 skipped

## Runtime split
- `backend/app/main.py` → reminder runtime
- `backend/app/worker.py` → SLA-only runtime

## Status
reminder runtime contour closed
