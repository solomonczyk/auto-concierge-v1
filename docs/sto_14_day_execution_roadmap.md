# Auto-Concierge — STO Launch Execution Roadmap (14 Days)

Start date: 10 March 2026
Primary goal: move from the current backend-ready state to a launch-ready STO product as fast as possible.

This roadmap is subordinate to:

`docs/PROJECT_EXECUTION_STRATEGY.md`

Use this roadmap for daily execution.

---

# Operating Rule

Each day must end with one of the following outcomes:

- a completed user-facing capability
- a completed operator-facing capability
- a verified launch-critical runtime improvement

No day should be spent on abstract refactoring unless it removes a launch blocker.

---

# Launch Target of This 14-Day Plan

By the end of Day 14 the system should have:

- working Telegram WebApp booking flow
- appointment creation from customer side
- appointment view / cancel / reschedule
- operator-side appointment handling
- booking confirmations
- reminder flow running
- stable deployment candidate

---

# Day 1 — Booking Flow Audit

Goal:

Confirm the exact current backend readiness for STO booking flow.

Tasks:

- verify Appointment model fields required for booking
- verify Service, Client, Tenant relations
- verify booking-related endpoints already available
- verify PublicBookingCreate / booking contracts
- identify missing launch-critical backend pieces only

Deliverable:

- short booking-flow audit note
- explicit list of missing pieces blocking Telegram WebApp booking

Done when:

- it is clear what already works
- it is clear what must be built next

---

# Day 2 — Service List for WebApp

Goal:

Make customer service selection work reliably.

Tasks:

- confirm or add endpoint for public service list
- ensure tenant-safe service retrieval
- verify response format for Telegram WebApp UI
- verify only active/allowed services are shown

Deliverable:

- working service list endpoint for WebApp
- tested payload for frontend use

Done when:

- customer can open WebApp and receive valid service list

---

# Day 3 — Available Slot Retrieval

Goal:

Make slot selection work.

Tasks:

- confirm or add endpoint for available slots
- validate timezone handling
- validate service duration usage
- verify slot filtering for reschedule flow
- verify slot conflict behavior

Deliverable:

- working slot endpoint
- confirmed slot payload for WebApp

Done when:

- customer can request valid slots for selected service/date

---

# Day 4 — Booking Creation from WebApp

Goal:

Customer can create appointment through Telegram WebApp.

Tasks:

- finalize public booking create endpoint behavior
- ensure client lookup/create works
- ensure appointment creation works
- ensure tenant-safe bot/notification path works
- verify confirmation message after booking

Deliverable:

- end-to-end booking creation from WebApp

Done when:

- new appointment is created successfully
- operator can see the created appointment
- customer receives confirmation

---

# Day 5 — Booking Read / Current Appointment View

Goal:

Customer can see current appointment.

Tasks:

- add or confirm endpoint for reading current appointment by customer identity
- ensure tenant-safe resolution by Telegram identity
- verify response schema for WebApp display
- show status, service, time, and key details

Deliverable:

- working current appointment endpoint

Done when:

- customer can open WebApp and see actual booking details

---

# Day 6 — Customer Cancellation Flow

Goal:

Customer can cancel appointment safely.

Tasks:

- add or finalize cancel action endpoint
- verify status transition rules
- verify appointment history update
- verify notification path
- verify operator view updates correctly

Deliverable:

- working client-side cancellation flow

Done when:

- cancellation works end-to-end
- status and notifications are correct

---

# Day 7 — Customer Reschedule Flow

Goal:

Customer can reschedule appointment.

Tasks:

- finalize reschedule endpoint/path
- reuse slot availability logic safely
- ensure old slot release / new slot booking is correct
- verify history and notifications

Deliverable:

- working client-side reschedule flow

Done when:

- customer can move appointment to another valid slot

---

# Day 8 — Operator Appointment List

Goal:

Operator can see appointments needed for daily work.

Tasks:

- confirm or add minimal appointment list endpoint/view
- verify filtering by date/status
- verify ordering and tenant isolation
- prepare minimal operator UI consumption contract

Deliverable:

- working operator appointment list

Done when:

- operator can reliably view appointments for current workday

---

# Day 9 — Operator Actions

Goal:

Operator can perform critical daily actions.

Tasks:

- confirm or finalize status update flow
- confirm reschedule from operator side
- confirm cancel from operator side
- verify notifications to customer

Deliverable:

- operator control path for status / cancel / reschedule

Done when:

- operator can fully manage appointment lifecycle

---

# Day 10 — Booking Confirmation & Notification Hardening

Goal:

Notifications are consistent for launch-critical booking events.

Tasks:

- verify appointment_created notification
- verify status-change notifications
- verify correct tenant bot routing
- verify failure does not break business flow
- verify retry path via outbox if applicable

Deliverable:

- stable booking notification behavior

Done when:

- notifications work for booking, cancel, reschedule, status changes

---

# Day 11 — Reminder Flow

Goal:

Automated reminders work.

Tasks:

- verify reminder scheduler/runtime
- verify 24h reminder logic
- verify 1h reminder logic
- verify message content and tenant bot routing

Deliverable:

- working reminder flow

Done when:

- reminders are generated and delivered for test appointments

---

# Day 12 — Core Freeze Readiness Check

Goal:

Confirm whether the booking lifecycle is stable enough to freeze the core.

Tasks:

- verify booking create / view / cancel / reschedule
- verify operator-side lifecycle management
- verify notifications and reminders
- confirm no launch-blocking architectural drift entered core

Deliverable:

- Core Freeze readiness decision

Done when:

- project can honestly say whether core snapshot is allowed

---

# Day 13 — Stabilization & Regression Day

Goal:

Reduce launch risk.

Tasks:

- run regression tests
- run booking lifecycle manual checks
- fix P0 issues only
- review logs for runtime errors
- verify background workers remain stable

Deliverable:

- cleaned launch candidate build

Done when:

- no unresolved P0 remains
- system is materially more stable than Day 12

---

# Day 14 — Launch Candidate Review

Goal:

Prepare decision for STO launch candidate.

Tasks:

- compare actual system against acceptance criteria
- classify remaining issues as P0 / P1 / P2
- decide go / no-go for launch window
- produce short launch-readiness report

Deliverable:

- launch readiness report
- next-step decision for production release or short hardening extension

Done when:

- it is clear whether the STO product is ready to launch

---

# Daily Reporting Format

At the end of each day, record:

- what was completed
- what remains blocked
- whether the roadmap day is fully closed
- whether the next day can start immediately

Recommended format:

`Day X — completed / partially completed / blocked`

---

# Priority Rule

When choosing between tasks, always prefer:

1. working booking flow
2. operator control
3. reminders and notifications
4. stability
5. cosmetic improvements last

---

# What Must Not Derail This 14-Day Plan

Do not spend roadmap time on:

- advanced SaaS onboarding
- billing
- analytics dashboards
- AI modules
- large architectural rewrites
- non-critical UI polish

These belong after STO product launch.

---

# Success Condition of the 14-Day Plan

The plan is considered successful if by the end of Day 14:

- customer booking lifecycle works end-to-end
- operator can manage bookings
- reminders work
- notifications work
- tenant isolation holds
- launch decision can be made from evidence, not assumptions

