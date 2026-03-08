# PLATFORM & PRODUCT STRATEGY

## Auto‑Concierge System

Date: 2026\
Version: 1.0\
Status: Strategic decision document

------------------------------------------------------------------------

# 1. Context

The Auto‑Concierge project was initially developed as a SaaS system for
**automotive service centers (СТО)** with functionality for:

-   appointment scheduling
-   slot availability management
-   workflow status control
-   Kanban-style operational board
-   notifications
-   integrations
-   multi‑tenant SaaS architecture

During development it became clear that the system architecture solves a
**broader class of problems**:

> management of bookings, resource availability, and operational
> workflows.

This means the platform can theoretically be applied to multiple
industries.

Examples:

-   medical clinics
-   beauty salons
-   service centers
-   equipment or room rental
-   education scheduling
-   field service operations

This raises a strategic question:

**Should the product immediately become a universal SaaS platform for
all industries?**

------------------------------------------------------------------------

# 2. Strategic Decision

The project will follow the model:

**Vertical Product + Platform Core**

and will **not** attempt to build a universal SaaS platform from the
start.

------------------------------------------------------------------------

# 3. Reasons for the Decision

## 3.1 Universal systems tend to expand uncontrollably

Although booking systems appear similar across industries, important
differences exist.

  Industry        Key differences
  --------------- ---------------------------------------
  Auto service    repair bay, mechanic, repair duration
  Clinic          doctor, room, repeat visits
  Beauty          specialist, service duration
  Rental          resource conflicts, buffers
  Field service   teams, travel routes, SLA

Approximately **70% of functionality overlaps**, but **30% diverges
significantly**, often affecting data models and workflows.

Trying to support all industries immediately dramatically increases
system complexity.

------------------------------------------------------------------------

## 3.2 Product truth must come from real usage

Before building a universal platform, the system must experience:

-   real operators
-   real workflows
-   real scheduling conflicts
-   real cancellations and rescheduling
-   real integration failures
-   real payment decisions by customers

This can only be obtained by focusing on a **specific vertical market
first**.

------------------------------------------------------------------------

## 3.3 Resource limitations

Simultaneously building:

-   a vertical SaaS product
-   a universal SaaS platform
-   a configurable platform core

effectively creates **three separate products**, which dramatically
increases risk and slows progress.

------------------------------------------------------------------------

# 4. Development Strategy

The system will evolve in **three logical layers**, but as **one
product**.

------------------------------------------------------------------------

# 5. Product Architecture Layers

## 5.1 Layer 1 --- Vertical Product

Initial product:

### Auto‑Concierge for Automotive Service

Core functionality:

-   client appointment booking
-   slot availability management
-   repair workflow status tracking
-   Kanban operations board
-   notifications
-   Telegram integration
-   operator interface

Goal:

-   validate product value
-   gain real operational feedback
-   acquire first paying customers

------------------------------------------------------------------------

## 5.2 Layer 2 --- Platform Core

In parallel, a **reusable platform core** will be developed beneath the
vertical solution.

This includes:

### Tenant System

-   multi‑tenancy
-   user roles
-   data isolation

### Client Management

-   client profiles
-   contact information
-   interaction history

### Resource Calendar

-   resources
-   availability windows
-   time slots

### Booking Engine

-   appointment creation
-   slot reservation
-   conflict detection

### Workflow Engine

-   state machine
-   lifecycle transitions

### Notification System

-   messaging
-   webhook integrations
-   external communication

### Reliability Layer

-   transactional outbox
-   retry logic
-   integration resilience

### Audit System

-   event logs
-   traceable data changes

This becomes the **long‑term platform core**.

------------------------------------------------------------------------

# 6. Critical Architecture Rule

The system must avoid hard‑coding automotive concepts in the platform
layer.

For example, the following must **not appear in platform‑level models**:

-   repair bay identifiers
-   vehicle models
-   mechanic shift logic

Industry‑specific elements belong only in the **vertical layer**.

------------------------------------------------------------------------

# 7. Disallowed Strategy

At the current stage the project **must not launch** a separate:

### Universal Booking SaaS

Reasons:

-   premature abstraction
-   complex configuration requirements
-   undefined product scope

A universal platform may only be considered **after a vertical product
succeeds**.

------------------------------------------------------------------------

# 8. Long‑Term Platform Expansion

After validating the first vertical market, additional vertical products
may be introduced:

### Clinic Concierge

medical appointment management

### Beauty Concierge

salons and personal services

### Service Concierge

field service scheduling

### Resource Booking Platform

general resource reservation

All will operate on the **same platform core**.

------------------------------------------------------------------------

# 9. Architecture Evolution

The expected development path:

Stage 1\
Vertical SaaS (Automotive service)

Stage 2\
Platform core stabilization

Stage 3\
Second vertical product launch

Stage 4\
Multi‑industry SaaS platform

------------------------------------------------------------------------

# 10. Strategic Rule

The development model follows:

**Vertical First → Platform Core → Expansion Later**

or

**Start with a niche → build a platform underneath → scale across
industries.**

------------------------------------------------------------------------

# 11. Development Implications

The codebase should be logically separated into:

### Vertical Layer

industry‑specific features (automotive service)

### Platform Layer

shared booking and workflow logic

### Infrastructure Layer

authentication, tenancy, integrations, reliability systems

------------------------------------------------------------------------

# 12. Expected Outcome

This strategy enables:

-   faster market entry
-   architectural flexibility
-   reduced risk of premature abstraction
-   a foundation for future multi‑industry expansion

------------------------------------------------------------------------

# Conclusion

Auto‑Concierge is not only a product for automotive services but a
**future operational workflow platform**.

However, development proceeds through a **focused vertical launch**,
while building a reusable platform core beneath it.
