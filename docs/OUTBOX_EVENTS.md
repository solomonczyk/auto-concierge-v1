# Outbox Event Contract

## appointment_created

- **entity_type:** `appointment`
- **payload:** `appointment_id`, `tenant_id`

## appointment_updated

- **entity_type:** `appointment`
- **payload:** `appointment_id`, `tenant_id`

---

Оба event type обрабатываются одним consumer-path: `handle_outbox_event(...)` → `run_appointment_integration_sync(...)`.
