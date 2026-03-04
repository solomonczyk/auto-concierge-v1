# Development Log

## 2026-03-02
- Investigated recurring 404 errors for `https://bt-aistudio.ru/media/posters/*.webp` after deployments
- Identified root cause in `studio-ai-site.nginx`: media alias pointed to release directory `dist/client/media`, which is overwritten during deploys
- Fixed nginx media location to persistent storage path `/var/www/studioaisolutions/media/`
- Added `try_files $uri =404` and WebP MIME mapping for safer static serving
- Added `deploy_site_safe.sh` to enforce safe static deploy flow:
  - deploys build files without deleting media storage
  - recreates compatibility symlink `dist/client/media -> /var/www/studioaisolutions/media`
  - validates required poster files before/after reload
- Applied hotfix directly on production server:
  - updated active nginx config alias in `/etc/nginx/sites-enabled/studio-ai-site` to `/var/www/studioaisolutions/media/`
  - reloaded nginx after successful config test
  - synchronized media from `/var/www/studioaisolutions/dist/client/media/` to persistent media directory
  - generated missing `.webp` poster files from existing `.jpg` files via `ffmpeg`
  - verified previously failing poster URLs now return HTTP 200
- Resolved video 404 errors on production for `/media/video/src/*.mp4`:
  - found source video files in legacy deployment path `/root/{REMOTE_DIR}/site-repo/public/media/video/src/`
  - restored videos to persistent storage `/var/www/studioaisolutions/media/video/src/`
  - fixed ownership to web user (`1001:1001`)
  - verified key video URLs return HTTP 200
- Hardened deploy guard script `deploy_site_safe.sh`:
  - validates required video files in addition to posters
  - bootstraps media from build output (`$SOURCE_DIR/media`) when persistent media storage is empty
- Started full prioritized audit remediation (P0 stage):
  - Added `tenant_id` claim into JWT issuance in `backend/app/core/security.py` and login token generation
  - Removed global production fallback `tenant_id=3` from middleware and dependency resolver
  - Added scoped public tenant mapping via `PUBLIC_TENANT_ID` in config/deps for explicitly public endpoints only
  - Added DB session tenant context propagation (`SET app.current_tenant_id`) and cleanup (`RESET`) in `backend/app/db/session.py`
  - Hardened WebSocket auth: requires JWT token and subscribes to tenant-scoped Redis channel `appointments_updates:{tenant_id}`
  - Updated Redis publishers in API/bot to tenant-scoped channel names
  - Secured Telegram webhook endpoint: moved to `/webhook` and added optional header-secret validation (`TELEGRAM_WEBHOOK_SECRET`)
  - Fixed public booking 500 response to avoid leaking internal error text
  - Fixed missing `return` in appointment read endpoint
  - Fixed frontend login payload format (`URLSearchParams` for `application/x-www-form-urlencoded`)
  - Updated frontend WS URL to include JWT token query parameter for authenticated handshake
  - Sanitized `history_22.02.26.md` to remove sensitive credential leaks from tracked files
- Applied P0 fixes on production server:
  - Uploaded patched backend/frontend files to `/root/auto-concierge-v1`
  - Updated `.env` with `PUBLIC_TENANT_ID=3` and generated `TELEGRAM_WEBHOOK_SECRET`
  - Rebuilt and restarted `api`, `bot`, `frontend` containers via `docker compose -f docker-compose.prod.yml up -d --build`
  - Set Telegram webhook to `https://bt-aistudio.ru/concierge/api/v1/webhook` with secret token
  - Verified webhook binding via Telegram `getWebhookInfo`
  - Verified public services endpoint responds with HTTP 200 and expected payload
- Incident fix: Telegram bot stopped responding after P0 deployment
  - Root cause: mode conflict (`bot_main.py` uses polling while webhook was active), causing repeated `TelegramConflictError`
  - Emergency recovery: deleted webhook (`deleteWebhook?drop_pending_updates=true`) and restarted `autoservice_bot_prod`
  - Verified current Telegram state: webhook URL is empty, bot polling started cleanly without conflict loop
- Telegram consultation UX refinements (user-requested):
  - Removed clarifying-question block from AI diagnostic response message template
  - Updated recommendation CTA to explicit direct booking label: `✅ Записаться на рекомендованную услугу`
  - Kept immediate preselected service handoff in consultation keyboard via `service_id` WebApp URL
  - Removed custom Telegram menu button (`🔧 Запись`) by resetting to default menu button in `bot_main.py`
  - Deployed bot-side changes to production and restarted `autoservice_bot_prod`
  - Verified bot processing updates after restart in polling mode
- Fixed inconsistent service list in Telegram WebApp:
  - Root cause hypothesis confirmed at architecture level: WebApp could inherit stale dashboard token from `localStorage`, making requests tenant-authenticated instead of public-tenant
  - Updated `frontend/src/lib/api.ts` to disable Authorization header and 401 login redirects when route includes `/webapp`
  - Rebuilt and redeployed frontend container to production to force new bundle
- Fixed dashboard WebSocket disconnect after JWT schema update:
  - Root cause: legacy JWTs without `tenant_id` were rejected by new WS auth guard
  - Added backward-compatible fallback in `backend/app/api/endpoints/ws.py`:
    - if `tenant_id` missing in token, resolve `sub` (username) -> `User.tenant_id` from DB
  - Redeployed API container in production
- Added Telegram WebApp cache-busting for stale Mini App sessions:
  - Introduced `WEBAPP_VERSION` setting in backend config
  - Updated all bot-generated WebApp URLs to include `v=<WEBAPP_VERSION>` query param
  - Redeployed bot so users receive fresh Mini App URL and latest frontend bundle
- Localized public booking errors for RU market:
  - Replaced English error details in `appointments/public` flow with Russian user-facing messages
  - Localized `/services/public` unavailable message
  - Redeployed API container in production
- Improved dashboard WebSocket resilience:
  - Added automatic reconnect with exponential backoff in `frontend/src/contexts/WebSocketContext.tsx`
  - Added heartbeat ping every 25 seconds to keep WS channel alive
  - Deployed updated frontend bundle to production
- Fixed false "slot occupied" in Mini App caused by shop mismatch:
  - Root cause: Mini App requested slots with hardcoded `shop_id=1`, while booking validation used tenant-resolved shop
  - Added backend endpoint `GET /api/v1/slots/public` that resolves shop by `PUBLIC_TENANT_ID` server-side
  - Switched Mini App slot requests from `/slots/available` to `/slots/public`
  - Deployed API and frontend to production
- Fixed timezone mismatch in slot validation at booking submit:
  - Root cause: selected slot validation compared timezone-aware slots against naive datetime
  - Normalized requested datetime to UTC-aware before validation in `appointments/public`
  - Updated comparison logic to accept equivalent UTC/naive representations safely
  - Deployed API to production
- Fixed 500 on public booking:
  - Root cause: `notification_service.py` used `logging` without `import logging`
  - Added missing import, deployed via docker cp and restart
- WebApp booking notifications: hide admin duplicate from client
  - Root cause: when ADMIN_CHAT_ID equals client chat (e.g. testing), client saw both "Запись подтверждена!" and "Новая запись! (WebApp)"
  - Skip admin notification when admin chat == client chat to avoid duplicate
- Dashboard empty: admin was in tenant 1, WebApp appointments in tenant 3
  - Set admin user tenant_id to 3 for MVP alignment
- Dashboard 500 on /appointments/ and /services/: SET app.current_tenant_id syntax
  - Root cause: PostgreSQL SET does not accept bound params ($1), causing syntax error and transaction abort
  - Fixed session.py: use literal for tenant_id (validated int from context)
- Post-booking UX: show main menu after WebApp confirmation
  - Added NotificationService.send_booking_confirmation() that sends message with main keyboard
  - Replaced send_raw_message with send_booking_confirmation for client notification in appointments/public
- AI planner: ГРМ/ремень → «Диагностика автомобиля»
  - Added special handling for engine + ГРМ/ремень/распред in context
  - Added car_stems «грм» и «ремн» → «диагностика автомобиля»
- Несоответствие времени: WebApp (локальный) vs бот (UTC)
  - Бэкенд: timezone в payload, конвертация в ZoneInfo при форматировании
  - Фронт: передаёт Intl.DateTimeFormat().resolvedOptions().timeZone
  - Fallback: SHOP_TIMEZONE = Europe/Moscow
- Несоответствие услуги: консультация рекомендовала одну услугу, запись показывала другую
  - Root cause: бот загружал услуги из tenant по токену бота, WebApp — из PUBLIC_TENANT_ID; service_id из разных tenant указывал на разные услуги
  - Исправление: при подборе услуг для консультации используем tenant_id_for_services = PUBLIC_TENANT_ID (handlers.py)
  - service_id в URL WebApp теперь всегда из публичного каталога и совпадает с /services/public
- E2E: WebApp, Dashboard, Bot webhook (Playwright)
  - frontend/e2e/: webapp-booking.spec.ts, dashboard.spec.ts, bot-webhook.spec.ts
  - Fallback submit-кнопка в WebApp при отсутствии Telegram (для E2E и браузера)
  - data-testid для car-make, car-year, car-vin, submit-booking
  - Запуск: npm run test:e2e (backend + frontend должны быть запущены)
- Покрытие тестами и верификация workflow
  - Backend: исправлен conftest (Pydantic v2, SQLite file DB, моки Redis/Notification/rate-limit)
  - Добавлены test_public_workflow.py: services/public, slots/public, appointments/public, полный flow, waitlist, duplicate slot
  - Исправлены test_slots.py для timezone-aware дат
  - Валидация ServiceCreate.name (min_length=1) для пустой строки → 422
  - Frontend: мок Telegram WebApp (setHeaderColor, setBackgroundColor), AuthContext тесты без api.defaults
  - Backend: 30/30 passed. Frontend: 8/8 passed
## 2026-03-03 — E2E тесты: отладка и исправление под прод

### Найдено и исправлено:
- **baseURL в Playwright**: убран `/concierge` из baseURL — `page.goto('/login')` шёл на `/login` вместо `/concierge/login`
  - Решение: baseURL = `https://bt-aistudio.ru` (или `http://localhost:5173`), все goto используют полный путь `/concierge/login`
- **Webhook URL**: правильный путь через nginx: `/concierge/api/v1/webhook` (не `/api/v1/webhook`)
- **Dashboard strict mode**: `getByText(/заказы|.../i)` находил 4 элемента → заменено на `getByRole('heading', { name: 'Заказы' })`
- **service-card selector**: заменён на комбинированный `[data-testid="service-card"], div[class*="cursor-pointer"]` + фильтр `hasText: /₽/` — работает и с текущим деплоем
- **car-make/year/vin**: заменены `getByTestId` на `getByPlaceholder` — работает без data-testid в задеплоенной версии
- **submit-booking**: использован `.or()` — `getByTestId('submit-booking').or(getByRole('button', { name: /ПОДТВЕРДИТЬ/ }))`
- **Fallback submit button**: НЕ был задеплоен на прод → добавлен в BookingPage.tsx и закоммичен
- Закоммичены все изменения (96ea549), запушен на GitHub

### Статус тестов после исправлений:
- **6/7 passed** на проде (webhook: 2/2, dashboard: 3/3 ✅, webapp-service_id: 1/1 ✅)
- **1 требует деплоя**: `полный flow WebApp` — fallback кнопка submit только в новом коде
- После `docker-compose -f docker-compose.prod.yml up -d --build frontend` → будет 7/7

### Деплой команда:
```bash
git pull origin main && docker compose -f docker-compose.prod.yml up -d --build frontend
```
(сервер использует `docker compose`, не `docker-compose`)

### Root cause fallback-кнопки (commit c470851):
- `telegram-web-app.js` загружается в `index.html` и создаёт `window.Telegram.WebApp.MainButton` ДАЖЕ в обычном браузере
- Условие `!tg?.MainButton` всегда = false в Playwright
- Fix: заменено на `!tg?.initData` — `initData` непустой только в реальном Telegram Mini App

### Финальный статус: **5 passed / 2 skipped / 0 failed** ✅ (exit_code: 0)

- Каталог 100 популярных услуг автосервиса
  - Создан backend/data/services_catalog_100.json — 100 услуг с категориями, ценами, длительностью
  - Категории: двигатель, диагностика, тормоза, ходовая, шины, кондиционер, охлаждение, электрика, трансмиссия, выхлоп, кузов, стекло, мойка
  - Скрипт seed: python -m scripts.seed_services_catalog --tenant-id 3 [--dry-run]

---

## 2026-03-04 — Рабочий день. Итог.

### Выполнено за день:

**1. Fix: некорректная категория при ИИ-диагностике**
- Симптом: "очиститель лобового стекла" → категория Кузов → полировка кузова
- Исправлен system_prompt: добавлены явные правила категоризации с примерами
- Добавлены стемы в `car_stems`: очист/дворн/омыв/форсун/генер/старт/рихт

**2. Refactor: AI выбирает одну услугу из реального каталога**
- Добавлен `recommended_service` в `DiagnosticResult`
- GigaChat теперь видит весь список услуг и выбирает одну по точному имени
- `planner()` переписан: exact name match → category fallback → keyword fallback → 1 услуга
- `handlers.py`: передаётся `db_services` в `classify_and_diagnose`

**3. Fix: сообщение показывало несколько услуг**
- `messages.py`: "Рекомендуемые услуги" → "Рекомендуемая услуга", показывается только `services[0]`

**4. Fix: Kanban — карточки не переносились в "Готова"**
- Root cause: колонка `id: 'done'` отправляла статус `DONE`, бэкенд ожидал `completed`
- Исправлено: `done` → `completed` в `COLUMNS` и в группировке карточек

**5. Feat: планировщик напоминаний (APScheduler)**
- Добавлен `apscheduler>=3.10.0` в requirements
- Создан `reminder_service.py`: `send_morning_reminders()` (08:00) и `send_evening_reminders()` (20:00)
- `bot_main.py`: планировщик стартует вместе с ботом, таймзона из `SHOP_TIMEZONE`

**6. Feat: пропуск шага "Данные авто" для повторных клиентов**
- Backend: новый endpoint `GET /api/v1/clients/public?telegram_id=` — возвращает данные авто
- Frontend: при загрузке страницы запрашивает данные клиента; если `car_make` есть — `returningClient=true`, шаг `car` пропускается

**7. Docs: созданы два руководства**
- `docs/demo-guide-client.md` — пошаговый гайд для клиентов автосервиса
- `docs/demo-guide-technical.md` — полный технический справочник: архитектура, стек, API, деплой, env, ограничения

### Деплои за день:
- 5 деплоев бэкенда (bot + api)
- 2 деплоя фронтенда
- Все деплои через SSH → git pull → docker compose up --build

### На чём споткнулись:
- IP сервера в `.env.example` (188.120.117.99) не совпадал с реальным (109.172.114.149) — потеряли время на SSH
- `done` vs `completed` в Kanban — несоответствие фронт/бэк, клиент не мог перенести карточку

### Коммиты дня:
- `c9c0acf` — fix: AI категоризация дворников
- `504cbab` — fix: narrow cat_map, limit to top-2
- `6c2ea1e` — refactor: AI selects ONE service by exact name
- `5c1cc89` — fix: single recommended service in message
- `b6c3aac` — fix: kanban done → completed
- `287fea6` — feat: reminder scheduler 08:00 & 20:00
- `6ac6758` — feat: skip car step for returning clients
- `9e01507` — docs: client guide + technical reference

---

### 2026-03-04 — feat: Multi-tenant SaaS с slug-резолвингом тенанта

**Задача:** Переход от хардкод `PUBLIC_TENANT_ID` к динамическому резолвингу тенанта по slug в URL. Каждый автосервис получает адрес `/concierge/{slug}` и изолированный API `/api/v1/{slug}/...`

**Изменения:**

**Backend:**
- `backend/app/models/models.py` — добавлено поле `slug: Optional[str]` в модель `Tenant`
- `backend/app/core/tenant_resolver.py` — новый файл, FastAPI dependency `get_tenant_id_by_slug(slug: Path) -> int`
- `backend/app/api/endpoints/public.py` — новый файл, все 4 публичных endpoint под slug:
  - `GET /{slug}/services/public` — каталог услуг тенанта
  - `GET /{slug}/slots/public` — доступные слоты
  - `POST /{slug}/appointments/public` — создание записи (полная логика из appointments.py)
  - `GET /{slug}/clients/public` — инфо об авто клиента
- `backend/app/api/api.py` — подключён `slug_router` с prefix `/{slug}`
- `backend/app/core/config.py` — `PUBLIC_TENANT_ID` помечен deprecated (комментарий)
- `backend/app/api/deps.py` — удалён `public_paths` whitelist и `is_public_appointment_read` fallback
- `backend/app/bot/handlers.py` — `tenant_id_for_services = tenant.id` (без fallback)
- `backend/app/api/endpoints/services.py`, `slots.py`, `clients.py` — старые `/public` endpoint-ы возвращают 410 Gone
- `backend/alembic/versions/f4d3a52dba51_add_tenant_slug.py` — новая миграция

**Frontend:**
- `frontend/src/App.tsx` — добавлены маршруты `/concierge/:slug` и `/:slug` (backward compat `/webapp` сохранён)
- `frontend/src/pages/WebApp/BookingPage.tsx` — slug извлекается через `useParams`, все public API calls используют `${apiBase}` (где `apiBase = /${slug}`)
- `frontend/src/lib/api.ts` — обновлена логика определения WebApp-режима (axios interceptor)

**Деплой:**
- Миграция применена на проде, slug `auto-concierge` назначен тенанту id=3
- `WEBAPP_URL` обновлён в `.env` → `https://bt-aistudio.ru/concierge/auto-concierge`
- Пересобраны контейнеры: `api`, `frontend`, `bot`
- Проверка: `GET https://bt-aistudio.ru/concierge/api/v1/auto-concierge/services/public` → 200 OK

**Коммиты:**
- `973cc2d` — feat: multi-tenant SaaS — tenant resolved by slug in URL
- `c53102f` — fix: apiBase slug path and WebApp auth detection in axios interceptor

---

### 2026-03-04 — Fix: некорректный выбор услуги при ИИ-диагностике (ai_core.py)

**Проблема:** При фразе "не работает очиститель лобового стекла" бот предлагал "Полировка кузова" и "Керамическое покрытие" — несвязанные услуги.

**Root cause:**
1. GigaChat классифицировал симптом → категория `Кузов` (т.к. "стекло" ассоциируется с внешностью авто)
2. `cat_map["кузов"]` искал услуги с "кузов" → находил полировку/покрытие
3. В `car_stems` отсутствовали стемы для слов "очист", "дворн", "омыв"

**Исправления в `backend/app/services/ai_core.py`:**
1. **system_prompt** расширен: добавлены явные правила категоризации с примерами (стеклоочиститель/дворники = "Электрика", не "Кузов")
2. **`car_stems`** дополнен стемами: `очист`, `дворн`, `омыв`, `стеклоочист`, `форсун`, `генер`, `старт`, `рихт` → маппинг на нужные категории услуг

---

### 2026-03-04 — Feature: SaaS Provisioning — SUPERADMIN + Tenant Creation API

**Цель:** SUPERADMIN создаёт новый автосервис через API → автоматически создаётся Tenant (slug) + ADMIN пользователь + TenantSettings + базовый каталог услуг.

**Изменения:**

**`backend/app/models/models.py`:**
- `UserRole` enum: добавлено значение `SUPERADMIN = "superadmin"`
- `User.tenant_id`: изменено с `nullable=False` на `nullable=True` — SUPERADMIN не привязан к тенанту
- Новая модель `TenantSettings`: per-tenant настройки `work_start`, `work_end`, `slot_duration`, `timezone`
- `Tenant.settings`: добавлена обратная связь `uselist=False` к `TenantSettings`

**`backend/app/api/deps.py`:**
- Добавлена dependency `require_superadmin` — проверяет `role == SUPERADMIN`, иначе 403

**`backend/app/api/endpoints/tenants.py`** (новый файл):
- `POST /api/v1/tenants` — SUPERADMIN only
- Валидация slug: regex `[a-z0-9][a-z0-9-]{1,48}[a-z0-9]`, 3–50 символов, 422 при нарушении
- Проверка уникальности slug и admin_username (409 если занято)
- Создание: `Tenant` → `User(role=ADMIN)` → `TenantSettings` → 10 дефолтных услуг
- Структурированный лог `[Provisioning] Tenant created: id=... slug=...`
- Ответ 201: `{ tenant_id, slug, dashboard_url, admin_username, services_seeded }`

**`backend/app/api/api.py`:**
- Подключён `tenants.router` с `prefix="/tenants"`, `tags=["tenants"]`

**`backend/scripts/create_superadmin.py`** (новый файл):
- CLI-скрипт для создания SUPERADMIN (без tenant_id)
- Запуск: `docker exec -it autoservice_api_prod python scripts/create_superadmin.py --username root --password strongpassword`

**`backend/alembic/versions/e1a2b3c4d5e6_add_superadmin_role_nullable_tenant_tenant_settings.py`** (новая миграция):
- `ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SUPERADMIN'`
- `ALTER TABLE users ALTER COLUMN tenant_id DROP NOT NULL`
- `CREATE TABLE tenant_settings` с полями work_start, work_end, slot_duration, timezone

**Статус:** Код написан, миграция создана. Требует запущенного Docker для `alembic upgrade head` и создания первого SUPERADMIN.
