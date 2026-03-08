# P1 Leak Migration Plan

## Goal

Move auto-service specific fields out of shared core models:

- `Client.car_make`
- `Client.car_year`
- `Client.vin`
- `Appointment.car_make`
- `Appointment.car_year`
- `Appointment.vin`

## Target Design

- Shared core models stay generic
- Auto-specific fields move to vertical extension tables

## Proposed Tables

### client_auto_profile

| Column      | Type         |
|-------------|--------------|
| id          | PK           |
| client_id   | FK → clients |
| car_make    | VARCHAR(100) |
| car_year    | INTEGER      |
| vin         | VARCHAR(17)  |
| created_at  | TIMESTAMPTZ  |
| updated_at  | TIMESTAMPTZ  |

### appointment_auto_details

| Column        | Type             |
|---------------|------------------|
| id            | PK               |
| appointment_id| FK → appointments|
| car_make      | VARCHAR(100)     |
| car_year      | INTEGER          |
| vin           | VARCHAR(17)      |
| created_at    | TIMESTAMPTZ      |
| updated_at    | TIMESTAMPTZ      |

## Migration Order

1. Add new extension tables
2. Backfill data from current core tables
3. Switch reads to extension tables
4. Switch writes to extension tables
5. Remove old columns from core models
6. Update tests
7. Run regression

## Risks

- Broken API reads
- Broken public booking flow
- Deleted record payload mismatch
- Migration/backfill consistency issues
- Bot/Telegram handlers depend on `car_*` — must be switched to extension tables
- Frontend/API response contract: clients expect `car_*` in JSON — preserve response shape during rollout (read from extension, serialize same)
- Optional join: `Client` may have no `client_auto_profile`, `Appointment` may have no `appointment_auto_details` — handle 0..1 relationship in reads

## Rule

No column removal until reads/writes are switched and regression passes.
