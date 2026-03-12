# Platform / Product Split Strategy

Документ описывает стратегию разделения системы Auto-Concierge на платформенные и продуктовые уровни.

## Цель стратегии

- сохранить стабильный core
- позволить создавать вертикальные продукты
- поддерживать кастомные внедрения
- подготовить систему к полноценному SaaS

## Архитектурные уровни системы

Система состоит из четырёх основных уровней:

```
SaaS Core
    ↑
Vertical Core (STO Core)
    ↑
Product Application (STO App)
    ↑
Distribution / SaaS Solution
```

Дополнительно существует Custom Layer для внедрений.

---

## 1. SaaS Core (Platform Layer)

### Назначение

SaaS Core — это платформенное ядро, независимое от конкретной отрасли.

Он обеспечивает инфраструктуру для любых вертикалей.

### Компоненты

SaaS Core включает:

- multi-tenant архитектуру
- tenant registry
- authentication / RBAC
- billing hooks
- onboarding
- bot registry
- telegram runtime
- worker infrastructure
- outbox
- event system
- notification infrastructure
- feature flags
- extension framework

### Важный принцип

SaaS Core не содержит доменной логики STO.

---

## 2. STO Core (Vertical Layer)

### Назначение

STO Core — это вертикальное ядро автосервиса.

Он реализует доменную модель и бизнес-процессы STO.

### Компоненты

- services
- clients
- appointments
- booking lifecycle
- slot calculation
- reminders
- operator workflow
- status machine
- STO notifications

### Важный принцип

STO Core использует SaaS Core, но не зависит от конкретного интерфейса.

---

## 3. STO App (Product Layer)

### Назначение

STO App — это конкретное приложение для автосервисов.

Это продукт, который используется:

- операторами
- клиентами
- владельцами STO

### Компоненты

- Telegram bot
- WebApp booking
- operator dashboard
- client interface
- UI workflows
- frontend
- product configuration

---

## 4. SaaS Solution (Distribution Layer)

### Назначение

SaaS Solution — это коммерческое SaaS-решение, предоставляемое клиентам.

Это не просто приложение, а инфраструктура для подключения клиентов.

### Компоненты

- onboarding STO
- tariff plans
- dedicated bot provisioning
- tenant configuration
- SaaS admin panel
- white-label configuration
- deployment tooling

---

## 5. Custom Layer

### Назначение

Custom Layer используется для индивидуальных внедрений.

Кастомные решения не должны изменять core.

### Примеры кастомизаций

- интеграции с CRM клиента
- нестандартные workflow
- дополнительные поля
- enterprise-логика
- специфические уведомления

### Принцип

```
core + extensions
```

**а не**

```
core + client specific hacks
```

---

## Стратегия разделения репозиториев

Разделение на отдельные репозитории должно происходить поэтапно.

Раннее разделение приводит к:

- сложной синхронизации
- дублированию кода
- хаосу версий

Поэтому используется **stage-based split strategy**.

### Stage 1 — Early Product Development

**Статус проекта**

- активная разработка
- архитектура формируется
- доменная модель стабилизируется

**Репозитории**

- main repository
- baseline snapshot

**Текущая структура**

- `auto-concierge` (main repo)
- `auto-concierge-baseline-2026-03` (archival snapshot)

**Статус:** ✔ текущая стадия проекта (пройдена)

---

### Stage 2 — Product Stabilization

Этап наступает после:

- Core Freeze
- Launch Candidate
- первых production запусков

**Цель**

Подготовка к разделению platform / product.

**Действия**

Начать логическое разделение кода:

- `/platform`
- `/verticals`
- `/apps`
- `/extensions`

Но всё ещё внутри одного репозитория.

---

### Stage 3 — Platform / Vertical Split

Этот этап выполняется после:

- стабилизации продукта
- появления нескольких внедрений
- начала SaaS-масштабирования

**Репозитории**

Создаются:

- `auto-concierge-platform-core`
- `auto-concierge-sto-core`
- `auto-concierge-sto-app`

**Разделение**

```
Platform Core
    ↓
Vertical Core
    ↓
Product App
```

---

### Stage 4 — SaaS Platform

Когда система становится полноценным SaaS.

Добавляется:

- `auto-concierge-saas-solution`

Он объединяет:

- SaaS Core
- Verticals
- Apps

---

### Stage 5 — Custom Ecosystem

Когда появляются кастомные внедрения.

Создаётся:

- `auto-concierge-custom`

Туда выносятся:

- клиентские интеграции
- enterprise extensions
- кастомные workflow

---

## Итоговая архитектура репозиториев

```
auto-concierge-platform-core
auto-concierge-sto-core
auto-concierge-sto-app
auto-concierge-saas-solution
auto-concierge-custom
```

---

## Текущий статус проекта

На момент документа:

- Core Freeze completed
- Launch Candidate prepared
- production runtime validated

Проект находится на этапе:

**Stage 2 — Product Stabilization**

Разделение репозиториев пока преждевременно.

---

## Когда начинать разделение

Разделение рекомендуется начинать после появления:

- второго vertical продукта
- нескольких кастомных внедрений
- SaaS onboarding

Это соответствует **Stage 3 — Platform / Vertical Split**.

---

## Основной принцип

**Сначала:**

- architecture maturity

**Потом:**

- repository split

**а не наоборот.**
