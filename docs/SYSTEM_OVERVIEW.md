# System Overview

## High-level architecture

Auto-Concierge Core состоит из следующих компонентов:

**Client Interfaces**
- Web UI (frontend/)
- Telegram Bot
- Public booking API

**Backend Platform**
- FastAPI application
- Multi-tenant logic
- Appointment lifecycle engine
- WebSocket event system
- Webhook processing

**Infrastructure**
- PostgreSQL (primary database)
- Redis (pub/sub, caching)
- Docker deployment

## Core Modules

backend/app:

- api/ — REST endpoints
- bot/ — Telegram integration
- core/ — settings, security
- db/ — database session and base
- models/ — SQLAlchemy models
- schemas/ — Pydantic schemas
- services/ — business logic

## Platform Layers

**Core**
- backend/
- frontend/

**Configs**
- configs/

**Extensions**
- extensions/

## Deployment

Production deployment uses:

- docker-compose.prod.yml
- nginx / reverse proxy
- backup scripts

## Observability

System includes:

- /health
- /ready
- /live
- /metrics
