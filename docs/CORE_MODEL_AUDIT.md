# Core Model Audit

Domain Model Audit: проверка соответствия текущих полей правилам CORE_FIELD_ADMISSION_RULE и CORE_DOMAIN_BOUNDARY.

---

## Client

| Field | OK in Core? | Reason |
|-------|-------------|--------|
| id | yes | platform identity |
| tenant_id | yes | multi-tenant core |
| full_name | yes | generic concept |
| phone | yes | generic contact |
| telegram_id | yes | generic channel identifier |
| created_at | yes | audit / lifecycle |
| deleted_at | yes | soft-delete pattern |
| deleted_by | yes | audit linkage |
| car_make | **no** | auto-service specific |
| car_year | **no** | auto-service specific |
| vin | **no** | auto-service specific |

---

## Appointment

| Field | OK in Core? | Reason |
|-------|-------------|--------|
| id | yes | platform identity |
| tenant_id | yes | multi-tenant core |
| shop_id | yes | location / venue (generic) |
| client_id | yes | booking concept |
| service_id | yes | catalog linkage (generic) |
| start_time | yes | booking slot |
| end_time | yes | booking slot |
| status | yes | workflow |
| completed_at | yes | workflow / lifecycle |
| notes | yes | generic |
| integration_status | yes | integration model |
| last_integration_error | yes | integration model |
| last_integration_attempt_at | yes | integration model |
| created_at | yes | audit / lifecycle |
| deleted_at | yes | soft-delete pattern |
| deleted_by | yes | audit linkage |
| car_make | **no** | auto-service specific |
| car_year | **no** | auto-service specific |
| vin | **no** | auto-service specific |
