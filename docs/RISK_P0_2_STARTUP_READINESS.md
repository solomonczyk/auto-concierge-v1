# P0 #2 — Startup-order / health readiness in production

## Status
API closed. Background runtime health semantics partial.

## Closed
- `api` starts only after `db` and `redis` are healthy.
- `api` healthcheck uses `/ready`.
- `/ready` verifies real dependency readiness:
  - PostgreSQL
  - Redis
- `/ready` returns `503` when dependencies are unavailable.
 - Shared readiness logic was extracted into `backend/app/core/readiness.py` and reused by API health endpoints.

## Remaining gap
Background processes are gated by `depends_on` at startup, but their container healthchecks only verify that PID 1 is alive:

- `worker` -> `kill -0 1`
- `bot` -> `kill -0 1`
- `scheduler` -> `kill -0 1`

This means the process can be marked healthy while being operationally degraded.

## Architectural conclusion
P0 #2 is closed for API startup-order/readiness, but not fully closed for background runtime health semantics.

## Next hardening target
Replace process-only healthchecks for background services with dependency-aware health probes, or explicitly accept process-liveness-only semantics and document that limitation.

