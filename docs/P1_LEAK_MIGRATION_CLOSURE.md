# P1 Leak Migration — Closure

## What was the leak

- **clients:** `car_make`, `car_year`, `vin`
- **appointments:** `car_make`, `car_year`, `vin`

## Where it moved

- **client_auto_profiles** — extension table per client
- **appointment_auto_snapshots** — snapshot storage at booking time

## What was removed

- Legacy ORM fields (core models)
- Legacy API flat fields (`car_make` / `car_year` / `vin` in responses)
- Legacy DB columns (final migration `d5e6f8a9b0c1`)

## Result

- Core schema is clean
- Dual-storage removed
- **P1 migration complete**
