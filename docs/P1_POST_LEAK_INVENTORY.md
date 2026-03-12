# P1 post-migration inventory: car_make / car_year / vin

All occurrences of `car_make`, `car_year`, `vin` in code and tests, classified.

---

## 1. List of files and lines

| File | Lines | Classification |
|------|--------|----------------|
| backend/app/api/endpoints/appointments.py | 48-50, 58-80, 89-91, 122-124, 173-175, 214-216, 1006-1008, 1184-1206, 1260-1262, 1279-1281, 951 | See below |
| backend/app/api/endpoints/clients.py | 28-30, 72-76 | See below |
| backend/app/api/endpoints/public.py | 44-66, 70-74, 91-93, 106-108, 137-139, 298-299, 310-335, 413-415, 423-425, 442-444, 448-453, 480, 632, 638-640 | See below |
| backend/app/bot/handlers.py | 60-82, 482-485, 577, 592 | OK |
| backend/app/models/auto_extensions.py | (model columns) | OK |
| backend/app/services/demo_workflow.py | 51-53, 102-104 | OK |
| backend/alembic/versions/b3352db051c2_*.py | 24-26, 40-43 | OK (extension table) |
| backend/alembic/versions/d5e6f8a9b0c1_*.py | 8, 23, 58-63 | OK (drop migration) |
| backend/alembic/versions/e1a2b3c4d5e6_*.py | 66 | False positive (“enum values”) |
| backend/tests/test_external_integration_fail_safe.py | 171, 177, 189, 282, 288 | See below |
| frontend/src/hooks/useUpdateAppointment.ts | 8-10 | Legacy residue |
| frontend/src/hooks/useAppointments.ts | 14-16 | Legacy residue |
| frontend/src/pages/WebApp/BookingPage.tsx | 125-130, 136, 188-202, 209, 238, 295-298, 392-394, 422, 439, 451 | Legacy residue |
| frontend/src/components/dashboard/KanbanBoard.tsx | 58, 62 | Legacy residue |
| frontend/src/contexts/WebSocketContext.tsx | 39 | False positive (no car_* / vin) |
| docs/*.md, development_log.md | various | OK (documentation) |

---

## 2. Classification

### OK — extension / snapshot / migrations / docs

- **backend/app/models/auto_extensions.py** — `ClientAutoProfile`, `AppointmentAutoSnapshot` columns.
- **backend/app/bot/handlers.py** — Reads form data, writes to `AppointmentAutoSnapshot`; params and snapshot fields are extension usage.
- **backend/app/services/demo_workflow.py** — Creates snapshots with car_*; extension usage.
- **backend/alembic/versions/b3352db051c2_*.py** — Defines extension table columns.
- **backend/alembic/versions/d5e6f8a9b0c1_*.py** — Drops legacy columns; migration only.
- **backend/app/api/endpoints/appointments.py** — Lines 48-50: build `AppointmentAutoInfo` from snapshot; 58-80: `_upsert_appointment_auto_snapshot` writes to snapshot. **OK extension/snapshot usage.**
- **backend/app/api/endpoints/clients.py** — Lines 72-76: read from `profile.car_make` etc. for display. **OK extension usage.**
- **backend/tests/test_external_integration_fail_safe.py** — 177, 189, 288: assert on `payload["auto_info"]` and `appointment.auto_snapshot`. **OK.**  
  (171, 282: request body still sends flat `car_make`/`car_year` — see legacy below.)
- **docs/** and **development_log.md** — Descriptions of leak/closure. **OK.**

### Legacy residue — to clean

- **backend/app/api/endpoints/appointments.py** — `AppointmentCreate`, `AppointmentUpdate`, `AppointmentPatch` (89-91, 122-124, 173-175) and clients-endpoint payload (1184-1206, 1260-1262, 1279-1281): API **input** still uses flat `car_make`/`car_year`/`vin` instead of nested `auto_info`. Docstring 951: “car_make, car_year, vin”. **Legacy residue.**
- **backend/app/api/endpoints/public.py** — `ClientCarInfo`, `PublicBookingCreate`, **`AppointmentRead`** (137-139) still have flat `car_make`/`car_year`/`vin`; `_enrich_appointment_auto_fields` sets them on `appt` for that response. **Legacy residue** (public API contract + dead setattr if we switch to auto_info).
- **backend/app/api/endpoints/clients.py** — `ClientCreate` (28-30): flat car_* in request. **Legacy residue.**
- **backend/tests/test_external_integration_fail_safe.py** — 171, 282: request body `json={"car_make": "Toyota"}`, `json={"car_year": 2021}`. **Legacy residue** (test sends flat; API still accepts it).
- **frontend/src/hooks/useUpdateAppointment.ts** — Type has `car_make?`, `car_year?`, `vin?`. **Legacy residue.**
- **frontend/src/hooks/useAppointments.ts** — `Appointment` type has `car_make?`, `car_year?`, `vin?` (API now returns `auto_info`). **Legacy residue.**
- **frontend/src/pages/WebApp/BookingPage.tsx** — State and payload use flat car_*; fills from `clientData?.car_make` etc. **Legacy residue.**
- **frontend/src/components/dashboard/KanbanBoard.tsx** — Uses `appointment.car_make`, `appointment.car_year`; should use `appointment.auto_info?.car_make` etc. **Legacy residue.**

---

## 3. One-line summary

**P1 has residue in:** public API schemas (public.py `AppointmentRead` + flat in Create/Update/Patch in appointments.py and clients.py); frontend types and UI (useAppointments, useUpdateAppointment, BookingPage, KanbanBoard); tests that send flat car_* in request body.
