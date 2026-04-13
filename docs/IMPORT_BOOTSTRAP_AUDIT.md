# Import Bootstrap Audit

Date: 2026-03-16  
Scope: backend/app

## Goal

Detect dangerous import-time side effects:

- Redis connections
- RQ Queue creation
- Bot runtime bootstrap
- Worker dependency coupling

## Findings

### Redis.from_url

1. bot/loader.py

RedisStorage.from_url used for FSM storage.

Status: **Expected runtime bootstrap**

Loader is used only by bot runtime.

Decision documented in:

BOT_LOADER_REFACTOR_DECISION.md


2. services/external_integration_service.py

REDIS_CONN = Redis.from_url(settings.REDIS_QUEUE_URL)

Status: **Acceptable**

redis-py uses lazy connection pools.  
Connection established only on first command.

Risk classified as **low operational risk**.


### RQ Queue creation

Found only inside functions:

services/external_integration_service.py

Queue instances created at runtime, not import time.

Status: **Safe**

## Conclusion

No critical import-time side effects detected.

Bootstrap architecture is considered **safe for production runtime**.
