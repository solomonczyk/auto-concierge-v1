# Auto-Concierge Core

AI-assisted appointment orchestration platform for service businesses.

## Project Model

This repository contains the **core platform**.

Architecture layers:

- **Core:** backend/, frontend/
- **Configs:** configs/
- **Extensions:** extensions/
- **Documentation:** docs/

## Baseline

Frozen baseline snapshot: `auto-concierge-baseline-2026-03`

See: [docs/BASELINE_MANIFEST.md](docs/BASELINE_MANIFEST.md)

## Architecture

[docs/CORE_ARCHITECTURE.md](docs/CORE_ARCHITECTURE.md)

## Customization rules

[docs/CUSTOMIZATION_RULES.md](docs/CUSTOMIZATION_RULES.md)

---

## Возможности

- 📅 **Управление записями** - Создание, редактирование, отмена записей
- 👥 **Клиентская база** - Хранение информации о клиентах
- 🔧 **Telegram бот** - Запись через бот и Mini App
- 🤖 **AI консультант** - Интеграция с GigaChat для консультаций
- 📊 **Дашборд** - Kanban и Calendar представления
- 👥 **Мультиарендность** - Несколько автосервисов на одной платформе
- 🔐 **Тарифные планы** - Ограничение количества записей по тарифу

## Архитектура

```
auto-concierge-v1/
├── backend/                 # FastAPI приложение
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── bot/            # Telegram бот
│   │   ├── core/           # Конфигурация, безопасность
│   │   ├── db/             # База данных
│   │   ├── models/         # SQLAlchemy модели
│   │   └── services/       # Бизнес-логика
│   ├── alembic/            # Миграции БД
│   ├── scripts/            # Утилиты
│   └── tests/             # Тесты
├── frontend/              # React приложение
└── docker-compose*.yml    # Docker конфигурация
```

## Технологии

### Backend
- **FastAPI** - Асинхронный веб-фреймворк
- **SQLAlchemy** - ORM с async поддержкой
- **PostgreSQL** - Основная база данных
- **Redis** - Кэширование и очереди
- **Aiogram** - Telegram бот фреймворк
- **GigaChat** - Russian AI для консультаций

### Frontend
- **React 18** - UI фреймворк
- **TypeScript** - Типизация
- **Vite** - Сборщик
- **Tailwind CSS** - Стилизация
- **React Router** - Маршрутизация
- **React Big Calendar** - Календарь
- **TanStack Query** - Управление состоянием сервера

## Быстрый старт

### Требования
- Docker и Docker Compose
- Node.js 18+ (для разработки frontend)
- Python 3.11+ (для разработки backend)

### Development

1. Клонировать репозиторий:
```bash
git clone <repository-url>
cd auto-concierge-v1
```

2. Создать `.env` файл:
```bash
cp .env.example .env
```

3. Запустить через Docker Compose:
```bash
docker-compose up -d
```

4. Открыть в браузере:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Production

1. Настроить переменные окружения в `.env`:
```env
ENVIRONMENT=production
SECRET_KEY=<сгенерируйте случайный ключ>
ENCRYPTION_KEY=<сгенерируйте Fernet ключ>
POSTGRES_PASSWORD=<сложный пароль>
TELEGRAM_BOT_TOKEN=<токен от @BotFather>
```

2. Запустить production сборку:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

## API Endpoints

### Аутентификация
- `POST /api/v1/login/access-token` - Получить токен

### Записи
- `GET /api/v1/appointments/` - Список записей
- `POST /api/v1/appointments/` - Создать запись
- `PATCH /api/v1/appointments/{id}` - Обновить запись
- `PATCH /api/v1/appointments/{id}/status` - Изменить статус

### Услуги
- `GET /api/v1/services/` - Список услуг
- `POST /api/v1/services/` - Создать услугу

### Клиенты
- `GET /api/v1/clients/` - Список клиентов

### Магазины
- `GET /api/v1/shops/` - Список магазинов

## Структура базы данных

```
┌─────────────────┐     ┌─────────────────┐
│     tenants    │     │  tariff_plans  │
├─────────────────┤     ├─────────────────┤
│ id              │     │ id              │
│ name            │     │ name            │
│ bot_token_hash  │────▶│ max_appointments│
│ tariff_plan_id  │     │ max_shops       │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌────────┬────────┬────────┬────────┬────────┐
│ users  │ shops  │clients │services│appointments
├────────┼────────┼────────┼────────┼────────┤
│tenant_id│tenant_id│tenant_id│tenant_id│tenant_id
│shop_id │ tenant_id│ tenant_id│ tenant_id│ shop_id
│        │         │         │         │ client_id
│        │         │         │         │ service_id
└────────┴────────┴────────┴────────┴────────┘
```

## Тестирование

```bash
# Backend тесты
cd backend
pytest

# Frontend тесты
cd frontend
npm test
```

## Разработка

### Создание миграции
```bash
cd backend
alembic revision --autogenerate -m "add new field"
alembic upgrade head
```

### Создание пользователя
```bash
cd backend
python scripts/create_user.py --username admin --password admin --role admin
```

## Лицензия

MIT License
