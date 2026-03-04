# Auto-Concierge — Техническое руководство

> Версия: 1.0 | Дата: март 2026

---

## Архитектура системы

```
┌─────────────────────────────────────────────────────┐
│                   КЛИЕНТ (Telegram)                  │
│           Bot Commands / WebApp (Mini App)           │
└───────────────────┬─────────────────────────────────┘
                    │ HTTPS / Webhook
┌───────────────────▼─────────────────────────────────┐
│              BACKEND (FastAPI + Python 3.11)         │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │  Bot     │  │  API     │  │  AI Core           │ │
│  │ (aiogram)│  │ (FastAPI)│  │ (GigaChat/OpenAI)  │ │
│  └──────────┘  └──────────┘  └────────────────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │ Scheduler│  │  Worker  │  │  Notifications     │ │
│  │(APSched) │  │  (RQ)    │  │  (bot.send_message)│ │
│  └──────────┘  └──────────┘  └────────────────────┘ │
└──────┬───────────────┬────────────────────────────────┘
       │               │ pub/sub
┌──────▼──────┐  ┌─────▼──────────────────────────────┐
│ PostgreSQL  │  │           Redis                     │
│  (данные)   │  │  (кэш слотов, очередь, WebSocket)  │
└─────────────┘  └────────────────────────────────────┘
                    │ WebSocket
┌───────────────────▼─────────────────────────────────┐
│           DASHBOARD (React + Vite, Nginx)            │
│         Kanban / Calendar / Clients / Settings       │
└─────────────────────────────────────────────────────┘
```

---

## Стек технологий

### Backend
| Компонент | Технология | Версия |
|-----------|-----------|--------|
| Framework | FastAPI | 0.109.0 |
| ORM | SQLAlchemy (async) | 2.0.25 |
| Migrations | Alembic | 1.13.1 |
| DB driver | asyncpg | 0.29.0 |
| Bot framework | aiogram | 3.26.0 |
| Task queue | RQ (Redis Queue) | 1.16.1 |
| Scheduler | APScheduler | 3.11.2 |
| AI (Russian) | GigaChat SDK | 0.2.0 |
| AI (English) | OpenAI | 2.24.0 |
| Auth | JWT (python-jose) | 3.3.0 |
| ASGI server | Uvicorn + Gunicorn | 0.27.0 |

### Frontend
| Компонент | Технология |
|-----------|-----------|
| Framework | React + Vite |
| UI | Shadcn UI + Tailwind CSS |
| State | TanStack Query (React Query) |
| Charts | — |
| Real-time | WebSocket (native) |
| Calendar | — (custom) |

### Infrastructure
| Компонент | Технология |
|-----------|-----------|
| Database | PostgreSQL 15 |
| Cache / Queue / Pub-Sub | Redis 7 |
| Reverse proxy | Nginx (внутри frontend контейнера) |
| Containerization | Docker + Docker Compose |
| CI/CD | Git push → SSH → docker compose up --build |

---

## Файловая структура

```
auto-concierge-v1/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── api.py              # Сборка всех роутеров
│   │   │   ├── deps.py             # Auth зависимости (JWT, tenant)
│   │   │   └── endpoints/
│   │   │       ├── appointments.py # Записи (CRUD + public)
│   │   │       ├── clients.py      # Клиенты + /public endpoint
│   │   │       ├── services.py     # Каталог услуг
│   │   │       ├── shops.py        # Магазины + статистика
│   │   │       ├── slots.py        # Расписание слотов
│   │   │       ├── login.py        # JWT авторизация
│   │   │       └── webhook.py      # Telegram webhook
│   │   ├── bot/
│   │   │   ├── handlers.py         # Все обработчики бота
│   │   │   ├── keyboards.py        # Клавиатуры
│   │   │   ├── loader.py           # Bot + Dispatcher инициализация
│   │   │   ├── messages.py         # Шаблоны сообщений
│   │   │   ├── states.py           # FSM состояния
│   │   │   └── tenant.py           # Tenant резолюция для бота
│   │   ├── core/
│   │   │   ├── config.py           # Settings (pydantic-settings)
│   │   │   ├── context.py          # Tenant context var
│   │   │   └── slots.py            # Логика генерации слотов
│   │   ├── db/
│   │   │   └── session.py          # AsyncSession фабрика
│   │   ├── models/
│   │   │   └── models.py           # SQLAlchemy модели
│   │   ├── services/
│   │   │   ├── ai_core.py          # AICore: classify + planner
│   │   │   ├── ai_service.py       # GigaChat / OpenAI клиент
│   │   │   ├── notification_service.py  # Отправка уведомлений
│   │   │   ├── redis_service.py    # Redis клиент
│   │   │   ├── reminder_service.py # Планировщик напоминаний
│   │   │   └── external_integration_service.py
│   │   └── main.py                 # FastAPI app + middleware
│   ├── alembic/                    # Миграции БД
│   ├── scripts/                    # Утилиты (seed, repair)
│   ├── bot_main.py                 # Точка входа бота (polling)
│   ├── worker.py                   # RQ worker точка входа
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard/          # Kanban, Calendar, Clients, Settings
│   │   │   ├── WebApp/
│   │   │   │   └── BookingPage.tsx # Mini App (публичный)
│   │   │   └── LoginPage.tsx
│   │   ├── components/
│   │   │   ├── dashboard/
│   │   │   │   ├── KanbanBoard.tsx
│   │   │   │   ├── CalendarView.tsx
│   │   │   │   └── AppointmentEditDialog.tsx
│   │   │   └── ui/                 # Shadcn компоненты
│   │   ├── hooks/                  # React Query хуки
│   │   ├── contexts/               # WebSocketContext
│   │   └── lib/
│   │       └── api.ts              # Axios instance + interceptors
│   ├── nginx.conf
│   └── Dockerfile
├── docs/
│   ├── demo-guide-client.md
│   └── demo-guide-technical.md
├── docker-compose.yml              # Dev
├── docker-compose.prod.yml         # Production
├── development_log.md
└── .env.example
```

---

## Docker Compose (Production)

### Сервисы

| Контейнер | Образ | Порты | Назначение |
|-----------|-------|-------|-----------|
| `autoservice_db_prod` | postgres:15-alpine | внутренний | База данных |
| `autoservice_redis_prod` | redis:7-alpine | внутренний | Кэш, очередь, pub/sub |
| `autoservice_api_prod` | ./backend | 8002:8000 | REST API + WebSocket |
| `autoservice_bot_prod` | ./backend | — | Telegram Bot polling + scheduler |
| `autoservice_worker_prod` | ./backend | — | RQ worker (внешние интеграции) |
| `autoservice_frontend_prod` | ./frontend | 127.0.0.1:8081:80 | React SPA через Nginx |

### Команды деплоя

```bash
# Полный деплой (все сервисы)
docker compose -f docker-compose.prod.yml up -d --build

# Только бэкенд (изменения в Python)
docker compose -f docker-compose.prod.yml up -d --build api bot

# Только фронтенд (изменения в React)
docker compose -f docker-compose.prod.yml up -d --build frontend

# Просмотр логов бота
docker logs autoservice_bot_prod -f

# Просмотр логов API
docker logs autoservice_api_prod -f
```

---

## Переменные окружения (`.env`)

```env
# База данных
POSTGRES_SERVER=db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_strong_password
POSTGRES_DB=autoservice

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Безопасность
SECRET_KEY=your_32char_min_random_key
ENCRYPTION_KEY=your_fernet_key  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_SECRET=optional_secret_header
ADMIN_CHAT_ID=123456789  # telegram_id администратора

# WebApp
WEBAPP_URL=https://your-domain.com/concierge
WEBAPP_VERSION=2026-03-04-1  # cache busting

# AI
GIGACHAT_CLIENT_ID=your_id
GIGACHAT_CLIENT_SECRET=your_secret
# или
OPENAI_API_KEY=sk-proj-...

# Multi-tenant
PUBLIC_TENANT_ID=1  # tenant_id для публичного каталога

# Сервис
ENVIRONMENT=production
SHOP_TIMEZONE=Europe/Moscow
WORK_START=9
WORK_END=18
SLOT_DURATION=30
```

---

## База данных

### Схема (ключевые модели)

```
Tenant (1) ──── (*) User
  │                │
  │                └── shop_id → Shop
  ├── (*) Shop
  ├── (*) Service
  ├── (*) Client
  └── (*) Appointment
            ├── client_id → Client
            ├── service_id → Service
            └── shop_id → Shop
```

### Миграции

```bash
# Создать миграцию
cd backend
alembic revision --autogenerate -m "description"

# Применить миграции
alembic upgrade head

# Откат
alembic downgrade -1
```

### Статусы записи (AppointmentStatus)

```
new → confirmed → in_progress → completed
              └──────────────→ cancelled
waitlist (отдельный поток)
```

---

## API — Быстрый справочник

### Авторизация

```bash
POST /api/v1/login/access-token
Content-Type: application/x-www-form-urlencoded

username=admin&password=secret
```

Ответ: `{ "access_token": "...", "token_type": "bearer" }`

Все защищённые эндпоинты требуют заголовок:
```
Authorization: Bearer <token>
```

### Ключевые эндпоинты

```
# Публичные (без авторизации)
GET  /api/v1/services/public              — каталог услуг
GET  /api/v1/slots/public?service_id=&date=  — свободные слоты
POST /api/v1/appointments/public          — создать запись из WebApp
GET  /api/v1/clients/public?telegram_id= — данные авто клиента

# Защищённые
GET    /api/v1/appointments/             — список всех записей
PATCH  /api/v1/appointments/{id}/status  — изменить статус
GET    /api/v1/clients/                  — список клиентов (CRM)
GET    /api/v1/shops/stats               — статистика
POST   /api/v1/services/                 — создать услугу
WebSocket /ws?token=                     — real-time обновления
```

---

## AI-модуль (ai_core.py)

### Поток обработки

```
User message
    │
    ▼
classify_and_diagnose(message, history, db_services)
    │  GigaChat API → strict JSON
    │  { category, urgency, confidence, summary,
    │    clarifying_question, recommended_service }
    │
    ├── confidence > 0.4 → planner(diagnosis, db_services)
    │       │
    │       ├── 1. Exact name match (recommended_service field)
    │       ├── 2. Category → search terms map (fallback)
    │       ├── 3. Keyword stems from user text (fallback)
    │       └── 4. "Диагностика автомобиля" (last resort)
    │               └── returns [1 Service]
    │
    └── confidence ≤ 0.4 → ai_service.get_consultation()
            Conversational reply + planner(context_text)
```

### Добавление новой категории

В `ai_core.py` → `cat_map`:
```python
cat_map = {
    "электрика": ["электрооборудования"],
    "ходовая": ["ходовой"],
    # добавить новую категорию:
    "кондиционер": ["кондиционер", "климат"],
}
```

И в `car_stems` для keyword-matching:
```python
car_stems = {
    "кондиц": "кондиционер",   # новый стем
    ...
}
```

---

## Планировщик напоминаний (APScheduler)

Запускается в процессе бота (`bot_main.py`):

| Job ID | Cron | Функция | Описание |
|--------|------|---------|---------|
| `morning_reminders` | `08:00 SHOP_TIMEZONE` | `send_morning_reminders()` | Напоминания на сегодня |
| `evening_reminders` | `20:00 SHOP_TIMEZONE` | `send_evening_reminders()` | Напоминания на завтра |

Критерии выборки: `status IN (new, confirmed)` + `client.telegram_id IS NOT NULL`

---

## WebSocket — real-time обновления

### Подключение (фронтенд)

```javascript
const ws = new WebSocket(`wss://domain/ws?token=${jwtToken}`)

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    // msg.type: NEW_APPOINTMENT | APPOINTMENT_UPDATED |
    //           STATUS_UPDATE | WAITLIST_ADD
}
```

### Публикация (бэкенд)

```python
await redis.publish(f"appointments_updates:{tenant_id}", json.dumps({
    "type": "STATUS_UPDATE",
    "data": { "id": appt.id, "status": appt.status.value }
}))
```

---

## Роли пользователей

| Роль | Возможности |
|------|------------|
| `ADMIN` | Полный доступ: CRUD услуг, клиенты, статистика, создание записей |
| `MANAGER` | Редактирование услуг, создание записей, Kanban, Calendar |
| `STAFF` | Просмотр и смена статуса, список клиентов |

---

## Multi-tenancy

Каждый тенант изолирован на уровне БД полем `tenant_id`. Middleware определяет тенант из:
1. JWT токена (`current_user.tenant_id`)
2. Context var (устанавливается middleware по заголовку/webhook)
3. `PUBLIC_TENANT_ID` для публичных эндпоинтов

> ⚠️ Риск: в текущей версии `PUBLIC_TENANT_ID` — это хардкод для одного тенанта. При масштабировании на несколько клиентов нужен tenant resolver по домену или subdomain.

---

## Типичные операции

### Добавить нового пользователя-администратора

```bash
docker exec -it autoservice_api_prod python scripts/create_user.py \
  --username admin2 \
  --password secret123 \
  --role admin \
  --tenant-id 1
```

### Заполнить каталог услуг

```bash
docker exec -it autoservice_api_prod python -m scripts.seed_services_catalog \
  --tenant-id 1
```

### Посмотреть логи планировщика

```bash
docker logs autoservice_bot_prod | grep "\[Reminder\]"
```

### Проверить здоровье API

```bash
curl https://your-domain.com/concierge/api/v1/health
# или
curl http://localhost:8002/health
```

---

## Известные ограничения (v1)

| # | Ограничение | Приоритет |
|---|------------|-----------|
| 1 | `PUBLIC_TENANT_ID` — один тенант на весь публичный API | High |
| 2 | JWT в `localStorage` (уязвим к XSS) | Medium |
| 3 | APScheduler не персистентный (после рестарта не восстанавливает пропущенные джобы) | Low |
| 4 | Нет rate limiting на WebSocket endpoint | Medium |
| 5 | AI prompt на английском, но данные на русском — возможны edge cases в классификации | Low |
| 6 | `docker compose up --build` пересобирает зависимости при каждом деплое фронта | Low |

---

## Мониторинг (рекомендации)

Сейчас мониторинга нет. Рекомендуется добавить:

```
Минимальный стек:
- Uptime: UptimeRobot (бесплатно) → /health endpoint
- Логи: Loki + Grafana или Sentry (Python SDK)
- Метрики: Prometheus + node_exporter
```

---

## Связаться с разработчиком

Проект: `github.com/solomonczyk/auto-concierge-v1`
Сервер: `109.172.114.149` (nikasal.fvds.ru)
Продакшн URL: `https://bt-aistudio.ru/concierge`

---

*Auto-Concierge v1 — Technical Reference*
