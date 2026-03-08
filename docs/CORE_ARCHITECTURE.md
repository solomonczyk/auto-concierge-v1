# Auto-Concierge Core Architecture

## Архитектурная модель

Проект разделён на три слоя:

### Core
Расположение:
- backend/
- frontend/

Содержит универсальную логику платформы:
- auth
- tenants
- users / roles
- clients
- appointments
- websocket
- webhook
- billing / limits
- observability

Core должен быть универсальным и не содержать клиентских кастомизаций.

---

### Configs
Расположение:
- configs/

Используется для настройки коробочной версии без изменения кода:

- branding
- feature flags
- tenant presets
- integration templates

Configs могут менять поведение системы, но не добавляют новую бизнес-логику.

---

### Extensions
Расположение:
- extensions/

Используется для клиентских доработок:

- CRM интеграции
- телефония
- кастомные workflow
- нестандартные отчёты
- дополнительные API

Extensions могут использовать core API, но core не должен зависеть от extensions.

---

## Главное правило

Core → не зависит от extensions  
Extensions → могут использовать core

---

## Цель архитектуры

Эта структура позволяет:

- поддерживать коробочную версию
- быстро создавать кастомные решения
- развивать продукт как SaaS
