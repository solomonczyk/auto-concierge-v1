# E2E тесты: WebApp, Dashboard, Bot Webhook

## CI (GitHub Actions)

Тесты гоняются автоматически при push/PR в `main`.

**Обязательно:** добавь секрет в GitHub → Settings → Secrets → Actions:
- `PLAYWRIGHT_ADMIN_PASS` — пароль админа дашборда (prod)

**Опционально** (Repository variables):
- `PLAYWRIGHT_BASE_URL` — default `https://bt-aistudio.ru`
- `PLAYWRIGHT_ADMIN_USER` — default `admin`
- `PLAYWRIGHT_SLUG` — default `auto-concierge`

При падении загружается артефакт `playwright-report` (HTML).

---

## Запуск на проде

```powershell
# PowerShell — подставь актуальные URL из своего деплоя
$env:PLAYWRIGHT_BASE_URL = "https://bt-aistudio.ru"
$env:PLAYWRIGHT_API_URL = "https://bt-aistudio.ru"
$env:PLAYWRIGHT_ADMIN_USER = "admin"
$env:PLAYWRIGHT_ADMIN_PASS = "твой_пароль"
npm run test:e2e
```

**Важно:**
- Проверь, что concierge и API реально доступны по этим адресам (nginx, routing).
- WebApp-тест создаёт реальную запись в БД.
- Webhook-тест шлёт фейковый Update; если TELEGRAM_WEBHOOK_SECRET задан — передай его в заголовке (или тест будет skip).

**Текущий прод bt-aistudio.ru:** /concierge отдаёт 404 от основного сайта; если concierge на другом пути/поддомене — поменяй PLAYWRIGHT_BASE_URL и PLAYWRIGHT_API_URL.

---

## Запуск локально

1. **Запусти backend и frontend:**
   ```bash
   # Вариант A: Docker
   docker-compose up -d

   # Вариант B: Локально
   # Терминал 1: backend
   cd backend && uvicorn app.main:app --reload

   # Терминал 2: frontend (проксирует /api на :8000)
   cd frontend && npm run dev
   ```

2. **Убедись, что в БД есть данные:**
   - `PUBLIC_TENANT_ID` в .env
   - Минимум 1 услуга и 1 shop для tenant
   - Пользователь admin/admin (или свои креды для dashboard)

3. **Запуск E2E:**
   ```bash
   cd frontend
   npm run test:e2e
   ```

## Тесты

| Файл | Сценарий |
|------|----------|
| `webapp-booking.spec.ts` | WebApp: выбор услуги → авто → дата/время → запись |
| `dashboard.spec.ts` | Dashboard: логин, переход в календарь |
| `bot-webhook.spec.ts` | Webhook: POST Update, idempotency |

## Переменные

- `PLAYWRIGHT_BASE_URL` — URL фронта (default: http://localhost:5173/concierge)
- `PLAYWRIGHT_API_URL` — URL API для bot-webhook (default: http://localhost:8000)
