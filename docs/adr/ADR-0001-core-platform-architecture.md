# ADR-0001: Core Platform Architecture

Date: 2026-03-13  
Status: Accepted

## Context

Auto-Concierge is a SaaS platform for appointment orchestration for service businesses.

The system must guarantee:

- safe concurrent booking
- stable webhook processing
- resilience against external integration failures
- multi-tenant isolation

The platform is built around an async FastAPI runtime with PostgreSQL and Redis.

## Decision

The core platform architecture is structured into the following layers:

Client Layer
- Telegram Bot
- Telegram WebApp
- Web Dashboard (React)

API Layer
- FastAPI endpoints
- request validation
- authentication

Service Layer
- booking lifecycle
- webhook runtime
- external integrations
- domain services

Persistence Layer
- PostgreSQL (primary data)
- Redis (runtime state, idempotency, queues)

External Systems
- Telegram Bot API
- AI services
- business integrations (1C, Alpha Auto)

Key guarantees:

- DB-level concurrency protection (EXCLUDE USING gist)
- webhook idempotency via Redis NX
- circuit breaker for external integrations
- timeout protection for external APIs
- health/readiness monitoring

## Consequences

Benefits:

- high resilience of webhook runtime
- protection against double booking
- safe integration failures
- scalable SaaS architecture

Trade-offs:

- Redis required for runtime safety
- external integrations must follow timeout contract
- circuit breaker requires monitoring

## Status

Core platform frozen at **Core Freeze milestone (March 2026)**.

Future features must be implemented **on top of the core platform**, without modifying core guarantees unless strictly required.
