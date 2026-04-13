# Auto‑Concierge — Rapid STO Product Launch Strategy

Date of plan start: 10 March 2026  
Primary objective: Launch a working STO product as fast as possible, then evolve it into a SaaS platform.

---

# Strategic Principle

The project will be developed in two stages:

1. **Rapid Vertical Product Launch (STO Product)**
2. **SaaS Platform Expansion**

The key rule:

> Core platform architecture must remain stable while product functionality grows.

---

# Phase 1 — STO Product Launch (Highest Priority)

**Goal:** deliver a working product for an auto service business that handles bookings through Telegram.

**Target:** a usable system that can operate in real conditions.

**Estimated duration:** 21–28 days from March 10, 2026

**Expected launch window:** March 31 – April 7, 2026

---

# Phase 1 Functional Scope

## Client Experience (Customer Side)

Customer interacts via Telegram.

**Features:**

- Telegram WebApp booking
- choose service
- choose available slot
- create appointment
- view appointment
- reschedule appointment
- cancel appointment

**Notifications:**

- booking confirmation
- reminder (1 day before)
- reminder (1 hour before)

**Statuses:**

- created
- confirmed
- completed
- cancelled

---

## Operator Control (Minimal Dashboard)

Interface for service operators.

**Functions:**

- list of appointments
- change appointment status
- reschedule appointment
- cancel appointment

This dashboard can initially be very simple.

---

# Phase 1 Development Timeline

## Stage 1 — Client Booking Flow

**Scope:**

- Telegram WebApp
- service selection
- slot selection
- booking
- booking management

**Estimated duration:** 10–14 days  
**Expected completion:** March 20–24, 2026

---

## Stage 2 — Operator Control

**Scope:**

- appointment list
- status management
- reschedule
- cancel

**Estimated duration:** 7–10 days  
**Expected completion:** March 27 – April 3, 2026

---

## Stage 3 — Basic Production Readiness

**Scope:**

- reminder scheduler
- stability checks
- logging
- deployment setup

**Estimated duration:** 3–5 days  
**Expected completion:** March 31 – April 7, 2026

---

# Phase 1 Result

A working STO system:

- clients book through Telegram
- operators manage appointments
- reminders work
- system runs in production

---

# Critical Architectural Moment — Core Freeze

After Stage 1 is completed and the full booking lifecycle works, the project must perform a **Core Platform Snapshot**.

**Estimated moment:** March 24–27, 2026

At this point:

> The platform core must be extracted and preserved as a stable layer.

---

# Core Platform Snapshot

The following components become **immutable core platform modules**:

- tenant system
- authentication
- database layer
- outbox event system
- background workers
- telegram bot runtime
- scheduler
- infrastructure services

These components must not contain vertical business logic.

A tagged snapshot must be created in the repository.

**Example tag:** `core-platform-v1`

---

# Platform Separation Structure

After the core snapshot, the repository structure should follow this model:

```
core/              # platform infrastructure
verticals/
  auto_service/    # STO business logic
  custom/          # client‑specific customizations
```

---

# Phase 2 — SaaS Platform Expansion

This phase starts after the STO product is already operational.

**Estimated start:** April 2026

---

# SaaS Expansion Roadmap

## Step 1 — Operator Dashboard Expansion

**Add:**

- kanban board
- workload visualization
- service management
- customer management

**Estimated duration:** 2–3 weeks

---

## Step 2 — SaaS Onboarding

Allow new businesses to connect automatically.

**Features:**

- tenant registration
- Telegram bot connection
- webhook configuration
- subscription plans

**Estimated duration:** 2–3 weeks

---

## Step 3 — SaaS Scaling

Future capabilities:

- AI operator assistant
- analytics
- integrations

---

# Development Operating Mode

To achieve the accelerated timeline:

- work daily
- prioritize working features over perfection
- avoid unnecessary UI complexity
- stabilize core infrastructure

---

# Primary Guiding Document

This document is the **primary execution strategy for the project** until the STO product launch is completed.

All development decisions must follow this roadmap.

---

# Planning Assumptions

This strategy is based on the following assumptions:

- work continues daily at the current delivery speed
- architecture-level blockers remain closed
- no major redesign is introduced before STO launch
- the team prioritizes release-critical scope over UI polish
- the first launch is for the STO product first, not full SaaS self-service

---

# What Is Fully Documented

The following is already explicitly documented in this strategy:

- launch priority: STO product first, SaaS second
- phase order
- launch target window
- stage-by-stage scope
- Core Platform Snapshot timing
- separation into core / vertical / custom layers
- post-launch SaaS expansion direction

---

# What Is Still an Estimate, Not a Guarantee

The following items are planning estimates and must be treated as operational targets, not guaranteed dates:

- 10–14 days for Client Booking Flow
- 7–10 days for Operator Control
- 3–5 days for Basic Production Readiness
- total launch window of March 31 – April 7, 2026

These dates are realistic only if release scope remains controlled.

---

# Mandatory Launch Gates Before STO Production Release

The STO product launch is considered ready only if all of the following are true:

- client booking flow works end-to-end
- reschedule and cancel flows work
- reminders run in production
- operator can view and manage appointments
- deployment is stable
- critical regression passes
- no unresolved blocker remains in booking, notification, status, or runtime flows

---

# Mandatory Core Snapshot Gate

The Core Platform Snapshot must be created only after the full booking lifecycle is proven operational.

**Minimum required condition for snapshot:**

- booking creation works
- appointment update works
- cancellation works
- reminders work
- operator-side status updates work

Only after that moment the core can be frozen and tagged.

---

# Execution Rule

Until STO launch is complete:

- every new task must justify its launch value
- non-critical SaaS features are deferred
- customizations must not mutate core directly
- architecture decisions must preserve future split into platform / vertical / custom

---

# Audit Conclusion

Current strategy status:

- documented: yes
- phase order defined: yes
- core freeze moment defined: yes
- launch window defined: yes
- assumptions explicitly stated: yes
- launch gates defined: yes

This means the strategy is documented at a level sufficient for execution and daily project control.

---

# Acceptance Criteria for STO Product Launch

The STO product is considered **ready for real-world launch** only if all the following criteria are satisfied.

## 1. Client Booking Flow

The customer must be able to:

- open the Telegram WebApp from the bot
- view available services
- select a date and time slot
- create an appointment

**Acceptance conditions:**

- booking is created successfully
- appointment appears in the operator view
- confirmation message is sent to the client

---

## 2. Appointment Management (Client Side)

The client must be able to:

- view an existing appointment
- cancel an appointment
- reschedule an appointment

**Acceptance conditions:**

- database state updates correctly
- operator view reflects the change
- client receives confirmation message

---

## 3. Appointment Management (Operator Side)

Operator must be able to:

- see list of appointments
- change appointment status
- reschedule appointment
- cancel appointment

**Acceptance conditions:**

- status updates persist in database
- client receives correct notification
- operator interface reflects updates immediately

---

## 4. Reminder System

Reminders must work automatically.

**Acceptance conditions:**

- reminder 24h before appointment
- reminder 1h before appointment
- message delivered to Telegram client

---

## 5. Notification Reliability

Notifications must not block core operations.

**Acceptance conditions:**

- booking succeeds even if notification fails
- errors are logged
- outbox system retries failed notifications

---

## 6. Multi‑Tenant Integrity

System must correctly isolate tenants.

**Acceptance conditions:**

- appointments belong to correct tenant
- correct Telegram bot sends notifications
- no cross‑tenant data leakage

---

## 7. Production Stability

Before launch the system must pass a stability check.

**Acceptance conditions:**

- system runs continuously for 24 hours
- no critical runtime errors
- background workers operate normally

---

## Launch Decision Rule

The STO product may be released only if:

- all acceptance criteria above pass
- no P0 or P1 bugs remain
- booking lifecycle works end‑to‑end

Only after these conditions are met the system can be considered **production ready**.

---

# Bug Severity Classification (Launch Control)

To avoid endless polish cycles, bugs are classified into three levels.

## P0 — Launch Blocker

Must be fixed before release.

**Examples:**

- booking cannot be created
- booking disappears or corrupts data
- reminders do not trigger
- wrong tenant receives data
- Telegram bot fails to send critical booking messages

**Rule:** Release **not allowed** with P0 bugs.

---

## P1 — Major Issue

Should be fixed before launch if possible.

**Examples:**

- occasional notification failure
- UI inconsistencies
- minor operator workflow friction

**Rule:** Release allowed **only if workaround exists**.

---

## P2 — Minor Issue

Does not block launch.

**Examples:**

- cosmetic UI issues
- minor performance inefficiencies
- non‑critical logging improvements

**Rule:** Deferred to post‑launch backlog.

---

# Scope Control Rules

To maintain delivery speed, the following scope rules apply until STO launch:

**Allowed additions:**

- fixes for booking lifecycle
- stability improvements
- operator usability improvements

**Not allowed before launch:**

- new vertical features
- analytics dashboards
- complex UI redesign
- advanced SaaS billing logic

---

# Core Snapshot Procedure

When the Core Freeze moment arrives the following steps must be executed:

1. Verify booking lifecycle works end‑to‑end
2. Run full test suite
3. Tag repository
4. Document core boundaries

**Example tag:** `core-platform-v1`

This snapshot becomes the **reference platform layer**.

---

# Development Execution Cadence

Development proceeds in short execution cycles.

**Cycle length:** 3–4 days

Each cycle must produce:

- one completed functional capability
- verified stability
- updated roadmap status

---

# Progress Checkpoints

Project progress should be reviewed at the following checkpoints.

| Checkpoint | Expected window |
|------------|-----------------|
| 1 — Client Booking Flow Complete | March 20–24 |
| 2 — Core Platform Snapshot | March 24–27 |
| 3 — Operator Control Ready | March 27 – April 3 |
| 4 — Production Stability Verification | March 31 – April 7 |

---

# Launch Metrics

Before launch the system should demonstrate:

- successful booking creation rate: 100% in internal testing
- reminder delivery success: >95%
- no cross‑tenant data leakage
- no P0 errors during 24h stability test

---

# Risk Factors

Potential risks that could delay launch:

- Telegram WebApp UX issues
- slot scheduling conflicts
- reminder scheduler misconfiguration
- operator workflow gaps
- single-resource scheduling limitation (one resource per shop) — see docs/RISK_SCHEDULING_1_SINGLE_RESOURCE_PER_SHOP.md

**Mitigation strategy:** address these early during Client Booking Flow stage.

---

# Strategic Alignment Check

This document has been verified against the intended project path:

1. launch STO product quickly
2. stabilize platform core
3. expand into SaaS

The strategy remains aligned with the project's primary objective: **rapid real‑world deployment followed by controlled SaaS expansion.**

---

# System Map (Auto‑Concierge Platform)

A high‑level map of the system so that development decisions always consider the full architecture.

---

## 1. Platform Core

Infrastructure modules that must remain stable and reusable.

**Modules:**

- tenant system
- authentication
- API framework
- database layer
- migrations
- configuration management
- logging
- metrics

**Purpose:** Provide a stable runtime environment for all vertical products.

---

## 2. Messaging & Telegram Runtime

Modules responsible for Telegram integration.

**Components:**

- bot registry
- multi‑bot runtime
- webhook processing
- Telegram handlers
- message dispatcher
- notification service

**Purpose:** Handle all Telegram interactions safely in a multi‑tenant environment.

---

## 3. Booking Domain (STO Vertical)

Business logic for auto service operations.

**Modules:**

- services catalog
- clients
- appointments
- scheduling
- status lifecycle
- reminders

**Purpose:** Implement the operational workflow of service bookings.

---

## 4. Operator Tools

Tools used by service staff.

**Modules:**

- appointment list
- operator actions
- status management
- rescheduling

**Purpose:** Allow staff to manage appointments efficiently.

---

## 5. Client Experience Layer

Customer interaction layer.

**Modules:**

- Telegram WebApp
- booking UI
- appointment management UI

**Purpose:** Provide a self‑service interface for customers.

---

## 6. Event System

Modules that ensure reliability of side‑effects.

**Components:**

- outbox table
- dispatcher
- worker runtime
- retry mechanism

**Purpose:** Guarantee reliable delivery of notifications and integrations.

---

## 7. Scheduler & Background Jobs

Responsible for asynchronous operations.

**Modules:**

- reminder scheduler
- periodic tasks
- background workers

**Purpose:** Handle tasks that must run outside the request cycle.

---

## 8. Deployment Layer

Infrastructure for running the system.

**Modules:**

- Docker configuration
- environment configuration
- CI/CD pipeline
- monitoring

**Purpose:** Provide reliable deployment and operations.

---

# Future System Domains (SaaS Expansion)

These domains will be added after the STO product launch.

---

## 9. SaaS Onboarding

**Modules:**

- tenant registration
- Telegram bot connection
- onboarding wizard

---

## 10. SaaS Billing

**Modules:**

- subscription plans
- payment processing
- usage tracking

---

## 11. Analytics

**Modules:**

- service load analytics
- booking statistics
- operational dashboards

---

## 12. AI Layer (Future)

**Modules:**

- AI operator assistant
- conversational automation
- predictive scheduling

---

# System Map Summary

**At launch the core running system consists of:**

- Platform Core
- Telegram Runtime
- Booking Domain
- Operator Tools
- Client Experience Layer
- Event System
- Scheduler

**After launch the system will expand with:**

- SaaS onboarding
- billing
- analytics
- AI modules

This map should be referenced whenever new features are proposed to ensure architectural consistency.
