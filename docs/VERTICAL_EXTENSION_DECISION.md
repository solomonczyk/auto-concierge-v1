# Vertical Extension Decision

## Decision

Auto-service specific fields are stored in **separate vertical extension tables**, not in shared core tables.

## Why

- Keeps platform core generic
- Prevents STO-specific columns from leaking into all future verticals
- Allows adding new verticals without polluting `Client` / `Appointment` core models

## Chosen Pattern

Use 0..1 extension tables linked to shared entities:

- `client_auto_profile` → `client_id`
- `appointment_auto_details` → `appointment_id`

## Alternatives Considered

### 1. Keep car_* in core tables

**Rejected**

- Pollutes shared models
- Blocks platform purity

### 2. JSONB in shared tables

**Rejected**

- Weaker schema control
- Harder validation
- Harder indexing
- Easier to accumulate хаос

### 3. Separate extension tables

**Accepted**

- Clean schema boundaries
- Explicit ownership of vertical data
- Easier future expansion for Clinic / Beauty / Service verticals

### 4. Generic key-value extension table

**Rejected**

One table `entity_attributes(entity_type, entity_id, key, value)` for all vertical attributes.

- Weak schema, no column-level validation
- Hard to query and index
- No FK / type safety
- Becomes a dump for unstructured data over time

## Rule

New vertical-specific fields must go to **vertical extension models** unless there is a strong cross-industry reason to keep them in core.
