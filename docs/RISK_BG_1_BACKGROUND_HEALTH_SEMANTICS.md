# Background health semantics for worker / bot / scheduler

## Status
Closed. Dependency-aware health probes implemented for worker, scheduler, and bot containers using shared readiness runner (app.core.health_probe).

## Problem
Background services currently use process-liveness-only healthchecks:

- `worker` -> `kill -0 1`
- `bot` -> `kill -0 1`
- `scheduler` -> `kill -0 1`

This proves only that the main process is alive, not that the service is operationally healthy.

## Why this matters
A service may be reported as healthy while:

- Redis is unavailable
- PostgreSQL is unavailable
- Telegram connectivity/configuration is broken
- internal loops are running but useful work is not being performed

## Current architecture
- Startup order is partially protected by `depends_on: condition: service_healthy` for `db` and `redis`.
- API readiness is already hardened through shared dependency-aware checks in `backend/app/core/readiness.py`.
- Background services do not yet reuse dependency-aware health semantics.

## Risk statement
Severity: P1
Operational degradation in background services can remain invisible to container health status.

## Candidate directions
1. Reuse shared readiness checks where applicable.
2. Introduce service-specific probes for background runtimes.
3. If full dependency-aware probes are not practical, explicitly document liveness-only semantics as an accepted limitation.

## Proposed next decision
Decide whether this is:
- a new P0 hardening item
- or a P1 operational resilience item

