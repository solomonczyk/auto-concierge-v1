Auto-Concierge v1 — Техническая документация
Обзор архитектуры и стека для технического отдела
Обзор системы
Auto-Concierge v1 — многопользовательская (multi-tenant) SaaS-платформа для управления автосервисами.

Сервер: 109.172.114.149
Docker Compose
👤 Клиент\nTelegram Bot
🖥️ Администратор\nWeb App
nginx\n(reverse proxy)
frontend\nnginx:alpine + React\n:8081
api\nFastAPI / uvicorn\n:8002
bot\nAiogram 3.x
worker\nBackground tasks
postgres:15\n:5432
redis:7\n:6379
☁️ GigaChat API\n(Сбер)
Технический стек
Слой	Технология	Версия
Backend	FastAPI + uvicorn	0.100+
ORM	SQLAlchemy (async)	2.x
Database	PostgreSQL	15
Cache / Queue	Redis	7
Bot	Aiogram	3.x
AI	GigaChat SDK (Сбер)	latest
Frontend	React + TypeScript	18
Build	Vite	5.x
Styling	Tailwind CSS	3.x
Auth	JWT (python-jose)	HS256
Encryption	Fernet (cryptography)	—
Container	Docker + Compose	v2
Proxy	nginx	1.29
Архитектура Multi-Tenancy
Изоляция данных реализована через PostgreSQL Row-Level Security (RLS) + ContextVar:

python
# app/core/context.py
tenant_id_context: ContextVar[Optional[int]] = ContextVar("tenant_id_context", default=None)
python
# app/db/session.py — устанавливается для каждой транзакции
await db.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
sql
-- alembic: RLS политика
CREATE POLICY tenant_isolation ON appointments
    USING (tenant_id = current_setting('app.current_tenant_id')::int);
IMPORTANT

Каждый запрос к БД выполняется в контексте tenant_id. Все таблицы с пользовательскими данными (shops, clients, appointments, services) используют RLS.

API Endpoints
POST   /api/v1/login/access-token     # Аутентификация (OAuth2 form)
GET    /api/v1/users/me               # Текущий пользователь
GET    /api/v1/shops/                 # Список магазинов
POST   /api/v1/shops/                 # Создать магазин
GET    /api/v1/services/              # Список услуг
POST   /api/v1/services/             # Создать услугу
GET    /api/v1/appointments/          # Список заказов
POST   /api/v1/appointments/          # Создать заказ
PATCH  /api/v1/appointments/{id}      # Обновить статус
GET    /api/v1/clients/               # Клиентская база
WS     /api/v1/ws                     # WebSocket (real-time обновления)
GET    /health                        # Health-check
Безопасность
python
# JWT токены
create_access_token(data, expires_delta)  # HS256, SECRET_KEY из env
# Пароли
get_password_hash(password)  # bcrypt
verify_password(plain, hashed)
# Шифрование bot tokens
encrypt_token(token)   # Fernet(ENCRYPTION_KEY)
decrypt_token(token)
# Rate limiting на /login
# 5 попыток / 1 минута (Redis-based)
WARNING

SECRET_KEY и ENCRYPTION_KEY должны быть уникальными на каждой инсталляции. ENCRYPTION_KEY — base64-encoded 32-byte Fernet key.

AI-интеграция (GigaChat)
python
# app/services/ai_service.py
async def get_completion(self, messages, services):
    payload = self._build_payload(messages, services)
    loop = asyncio.get_event_loop()
    # Синхронный SDK запускается в executor чтобы не блокировать event loop
    response = await loop.run_in_executor(None, lambda: self._client.chat(payload))
    return response.choices[0].message.content
python
# app/services/ai_core.py — два режима
classify(message)    # intent: booking / consultation / other
diagnose(symptoms)   # LLM анализ → список диагнозов
planner(diagnosis, services)  # матч диагнозов с услугами из БД
Структура проекта
auto-concierge-v1/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/        # shops, appointments, services, login
│   │   │   └── deps.py           # FastAPI Dependencies (auth, tenant)
│   │   ├── bot/
│   │   │   └── handlers.py       # Aiogram handlers
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic Settings
│   │   │   ├── security.py       # JWT, bcrypt, Fernet
│   │   │   └── context.py        # tenant_id ContextVar
│   │   ├── db/
│   │   │   └── session.py        # async SQLAlchemy + RLS setup
│   │   ├── models/
│   │   │   └── models.py         # ORM: Tenant, User, Shop, Client, Appointment
│   │   └── services/
│   │       ├── ai_service.py     # GigaChat wrapper
│   │       └── ai_core.py        # classify / diagnose / planner
│   ├── alembic/                  # Migrations (RLS policies included)
│   └── tests/
│       ├── conftest.py           # pytest fixtures (async SQLite)
│       └── test_security.py
├── frontend/
│   ├── src/
│   │   ├── pages/                # Login, Dashboard, Calendar, Clients, Settings
│   │   ├── components/           # UI компоненты
│   │   └── lib/api.ts            # axios, baseURL = BASE_URL + "api/v1"
│   ├── vite.config.ts            # base: "/concierge/"
│   └── nginx.conf                # SPA fallback: location / → /index.html
└── docker-compose.prod.yml       # 6 сервисов
Деплой
Продакшн: bt-aistudio.ru/concierge
bash
# Сервисы Docker Compose
autoservice_db_prod        postgres:15      (internal)
autoservice_redis_prod     redis:7          (internal)
autoservice_api_prod       FastAPI          127.0.0.1:8002
autoservice_worker_prod    background jobs  (internal)
autoservice_bot_prod       Aiogram bot      (internal)
autoservice_frontend_prod  nginx+React      127.0.0.1:8081
nginx (bt-aistudio.ru) — ключевые location:
nginx
location /concierge/ {
    proxy_pass http://127.0.0.1:8081/;   # SPA (без /concierge/ — strip prefix!)
}
location /concierge/api/v1/ws {
    proxy_pass http://127.0.0.1:8002/api/v1/ws;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
location /concierge/api/ {
    proxy_pass http://127.0.0.1:8002/api/;
}
NOTE

sites-enabled/studio-ai-site — обычный файл, не symlink. Изменения нужно вносить в sites-enabled напрямую, затем копировать в sites-available для бэкапа.

Обновление деплоя:
bash
cd /root/auto-concierge-v1
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker exec autoservice_api_prod alembic upgrade head
Исправленные баги (v1.0.1)
#	Файл	Описание	Severity
1	
shops.py
NameError: func not defined при POST /shops/	🔴 Critical
2	
security.py
, 
models.py
datetime.utcnow() deprecated (Python 3.12+)	🟡 Warning
3	
ai_service.py
Синхронный GigaChat вызов блокировал event loop	🔴 Critical
4	
conftest.py
Shop
 без 
tenant_id
, роль как строка вместо enum	🟡 Medium
Переменные окружения (.env)
bash
# Database
POSTGRES_SERVER=db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_DB=autoservice
# Redis
REDIS_HOST=redis
# Security
SECRET_KEY=...           # JWT signing (min 32 chars)
ENCRYPTION_KEY=...       # Fernet key (base64 32 bytes)
# Telegram
TELEGRAM_BOT_TOKEN=...
# AI
GIGACHAT_CLIENT_ID=...
GIGACHAT_CLIENT_SECRET=...
# App
ENVIRONMENT=production
ACCESS_TOKEN_EXPIRE_MINUTES=480
Известные ограничения и следующие шаги
NOTE

Текущее состояние: MVP v1.0, полностью рабочий продакшн.

Технический долг:

 WebSocket наличие проверить после nginx конфига (возможно нужна доп. настройка)
 Pytest тесты запустить на CI (SQLite in-memory fixtures готовы)
 Алибик миграции: проверить RLS политики на продакшн БД
 Rate limiting: перенести из кода в nginx (более надёжно)
Roadmap v1.1:

 SMS/Email уведомления (сейчас только Telegram)
 Интеграция с внешними CRM через webhook (external_integration_service.py готов)
 Мобильное приложение (API уже REST-совместим)
 Метрики: Prometheus + Grafana