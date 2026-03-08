# Baseline Manifest — Auto-Concierge Core

Архивный паспорт frozen-baseline версии. Фиксирует точную точку восстановления продукта, связку code/runtime/data/docs и правила проверки восстановленного состояния.

---

## 0. Baseline status

| Поле | Значение |
|------|----------|
| **Статус** | Frozen / Read-only |
| **Назначение** | Restore point, audit reference, source for future core refactor |
| **Допустимые изменения** | Только документирование, без функциональных изменений |

---

## 1. Versioning

| Поле | Значение |
|------|----------|
| **Название baseline** | `v1.0-core-baseline` |
| **Дата** | 2026-03-07 |
| **Git tag** | `v1.0-core-baseline` |
| **Commit hash** | `b1bddbe0d6c9661e31b7b70f7f826592aa5cc47f` (short: `b1bddbe`) |
| **Baseline branch** | `release/core-baseline` |
| **Docker image tag** | `auto-concierge:mvp-baseline-2026-03-07` |

---

## 2. Artifacts

| Артефакт | Путь / Имя |
|----------|------------|
| **Code snapshot** | Read-only snapshot repo: `auto-concierge-baseline-2026-03` |
| **Docker image tag** | `auto-concierge:mvp-baseline-2026-03-07` |
| **Docker archive** | `artifacts/auto-concierge_mvp-baseline-2026-03-07.tar` |
| **Docker archive size** | 395 MB |
| **DB backup** | `backups/baseline_2026_03_07.dump` |
| **DB backup size** | 0.04 MB (37 KB) |
| **Alembic head** | `b7c8d9e0f1a2` (add_completed_at_to_appointments) |

> **Runtime snapshot:** Docker image и .tar — это **backend baseline** (api, worker, bot). Frontend собирается отдельным образом и остаётся отдельным артефактом runtime.

---

## 3. Includes (что входит в baseline)

### Application scope

- [ ] **Auth:** JWT, cookie-based, tenant-scoped
- [ ] **Tenants:** multi-tenant, RLS, tenant resolver
- [ ] **Users / Roles:** superadmin, admin, manager, staff (см. UserRole в models.py)
- [ ] **Clients:** CRUD, tenant isolation
- [ ] **Appointments:** CRUD, status lifecycle, state machine
- [ ] **Status lifecycle:** new → confirmed → in_progress → completed / waitlist / cancelled / no_show
- [ ] **WebSocket:** tenant-scoped `appointments_updates:{tenant_id}`, WS ticket auth
- [ ] **Webhook:** Telegram webhook, secret validation, rate limit
- [ ] **Public flow:** /services/public, /slots/public, /appointments/public
- [ ] **Billing / Limits:** plan limits foundation, usage tracking

### Infrastructure scope

- [ ] **Deploy pack:** docker-compose.prod.yml, backup/restore scripts
- [ ] **Observability:** /health, /ready, /live, /metrics, structured logging

### Validation scope

- [ ] **E2E:** smoke test (login → /me → create appointment → patch status → WS → webhook → logout)

### Documentation scope

- [ ] **Docs:** RUNBOOK, PRODUCTION_CHECKLIST, BACKUP_RESTORE, contracts

---

## 4. Excludes (что вне scope baseline)

- [ ] Клиент-специфичные интеграции (CRM, 1С, телефония)
- [ ] Кастомные поля карточки клиента
- [ ] Нестандартные отчёты
- [ ] Боевые данные и персональные данные в backup
- [ ] Локальные secrets, production .env, private keys, сертификаты

---

## 5. Included fixes & operational requirements

### A. Included fixes

| Фикс | Статус |
|------|--------|
| Webhook mode vs polling conflict | Polling mode используется (webhook отключён) |
| JWT tenant_id fallback | Fallback: sub → User.tenant_id из DB при отсутствии claim |

### B. Operational requirements

| Требование | Описание |
|------------|---------|
| PUBLIC_TENANT_ID | Обязателен для public flow (/services/public, /slots/public, /appointments/public) |
| TELEGRAM_WEBHOOK_SECRET | Обязателен, если включён webhook mode; не требуется для polling mode |
| Redis AOF | AOF включён (`--appendonly yes`). Redis ephemeral — не критичен для restore. |
| Polling vs webhook | Baseline работает в polling mode; webhook требует отдельной настройки |

---

## 6. Restore proof (как проверить, что baseline живой)

### 6.1 Restore inputs (входные артефакты для восстановления)

| Артефакт | Описание |
|----------|----------|
| **Snapshot repo** | Read-only клон кода на commit baseline |
| **Docker image tag** | `auto-concierge:mvp-baseline-2026-03-07` |
| **DB backup file** | `backups/baseline_2026_03_07.dump` |
| **Env template** | `.env.example.production` или `.env.example` |
| **Nginx/site config** | `nginx-auto-concierge.conf` (если применимо) |

### 6.2 Health checks

```bash
curl -s http://localhost:8002/health
curl -s http://localhost:8002/ready
curl -s http://localhost:8002/live
```

### 6.3 Smoke flow (эталонный путь)

1. `POST /api/v1/login/access-token` → cookie set
2. `GET /api/v1/me` → user info with tenant
3. `POST /api/v1/appointments/` → appointment created
4. `PATCH /api/v1/appointments/{id}/status` → status updated
5. WS receives `appointment_status_updated` в канале `appointments_updates:{tenant_id}`
6. Webhook processed (если webhook mode)
7. `POST /api/v1/auth/logout` → cookies cleared

### 6.4 Backend smoke test

```bash
cd backend && pytest tests/test_smoke_e2e.py -v
```

### 6.5 Frontend E2E (опционально)

```bash
cd frontend && npm run test:e2e
```

---

## 7. Связка артефактов

```
git tag: v1.0-core-baseline
    ↓
commit: b1bddbe0d6c9661e31b7b70f7f826592aa5cc47f
    ↓
docker image: auto-concierge:mvp-baseline-2026-03-07
    ↓
db backup: backups/baseline_2026_03_07.dump
    ↓
docs: BASELINE_MANIFEST.md, RESTORE_FROM_BASELINE.md
```

---

## 8. Ссылки

| Документ | Путь |
|----------|------|
| Restore contract | `docs/RESTORE_FROM_BASELINE.md` |
| Customization rules | `docs/CUSTOMIZATION_RULES.md` |
| Runbook | `docs/RUNBOOK.md` |
| Backup/Restore | `docs/BACKUP_RESTORE.md` |
| Production checklist | `docs/PRODUCTION_CHECKLIST.md` |
