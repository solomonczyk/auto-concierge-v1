# Controlled STO Launch Plan

**Stage:** Post Day-14 Launch Candidate

Документ описывает, как продукт Auto-Concierge будет внедряться в реальные автосервисы (СТО) в контролируемых условиях.

Цель — не массовый запуск, а безопасная валидация в реальной среде.

---

## Launch Philosophy

Первые внедрения должны приоритизировать:

- **stability** — стабильность
- **observability** — наблюдаемость
- **learning from real operator behavior** — обучение на реальном поведении операторов
- **safe rollback capability** — возможность безопасного отката

Первые клиенты-СТО — это партнёры по валидации, а не анонимные пользователи.

---

## Launch Model

Запуск следует модели постепенного rollout:

```
Internal testing
    ↓
1 pilot STO
    ↓
3 STO group
    ↓
5–10 STO early network
    ↓
open onboarding
```

Каждый этап должен быть валидирован перед переходом к следующему.

---

## Phase 1 — Internal Validation

**Duration:** 2–3 дня

**Goal:** Убедиться, что система работает end-to-end в реалистичных сценариях.

**Tests:**

- **Customer side:** открыть бота → WebApp → выбрать услугу → слот → создать запись → просмотр → отмена → перенос
- **Operator side:** список записей → смена статуса → confirm → no_show → completed
- **Automation:** evening, morning, one-hour reminders
- **Deployment:** API uptime, scheduler jobs, worker jobs, Redis queue

**Exit criteria:** Все flow работают без критических ошибок.

---

## Phase 2 — Pilot STO

**Duration:** 1 неделя

**Participants:** 1 реальный автосервис

**Characteristics:** дружественный партнёр, готовность сообщать о проблемах, умеренный поток записей.

**Goals:** Валидировать реальный операторский workflow.

**Focus:** operator usability, booking reliability, reminder delivery, notification clarity.

**Metrics:** successful bookings, booking failures, slot conflicts, notification failures.

**Daily check:** logs review, operator feedback, bug triage.

**Exit criteria:** Система обрабатывает реальные записи без операционной нестабильности.

---

## Phase 3 — Early STO Group

**Duration:** 1–2 недели

**Participants:** 3 СТО

**Goals:** Валидировать multi-tenant поведение в реальном использовании.

**Focus:** tenant isolation, notification routing, scheduler stability, appointment lifecycle.

**Metrics:** average bookings per day, scheduler stability, failed notifications, operator adoption.

**Infrastructure checks:** DB load, Redis usage, worker stability.

**Exit criteria:** Нет cross-tenant проблем, стабильная работа reminders.

---

## Phase 4 — Early STO Network

**Duration:** 2–4 недели

**Participants:** 5–10 СТО

**Goals:** Валидировать масштабируемость и надёжность.

**Focus:** operational stability, onboarding repeatability, operator workflow improvements.

**Actions:** начать документировать процесс onboarding, уточнять configuration flows, готовить SaaS onboarding automation.

**Metrics:** daily active operators, bookings per STO, cancellation rate, reminder success rate.

**Exit criteria:** Система стабильно поддерживает несколько СТО без ручного вмешательства.

---

## Launch Metrics

| Категория | Метрики |
|-----------|---------|
| **Booking** | bookings created, booking failures, slot conflicts |
| **Notification** | confirmation sent, reminder sent, notification errors |
| **Operator** | operator actions, status transitions, appointment lifecycle completion |
| **System** | API error rate, scheduler job failures, worker queue backlog, Redis latency, DB query latency |

---

## Monitoring Strategy

**Sources:** application logs, Prometheus metrics, scheduler logs, worker logs, telegram delivery feedback.

**Daily routine:** review logs → review errors → review operator feedback → triage bugs.

---

## Incident Handling

При критическом инциденте:

1. Остановить onboarding новых СТО
2. Изолировать затронутый tenant
3. Применить hotfix
4. Валидировать фикс внутренне
5. Возобновить rollout

**Rollback:** система должна допускать временный ручной fallback для pilot STO при необходимости.

---

## Bug Classification During Launch

| Приоритет | Тип | Примеры | Реакция |
|-----------|-----|---------|---------|
| **P0** | critical | booking impossible, data corruption, cross-tenant leak, crash | Immediate fix |
| **P1** | serious | incorrect reminder timing, minor UI, notification wording | Fix in next patch |
| **P2** | improvement | UX polish, analytics, automation | Post-launch backlog |

---

## Operator Feedback Loop

Каждый партнёр должен давать feedback по:

- booking clarity
- operator workflow
- reminder usefulness
- notification quality

**Частота:** каждые 2–3 дня (pilot), еженедельно (early network).

---

## Technical Readiness for Scaling

Перед open onboarding необходимо подтвердить:

- scheduler stability
- worker queue stability
- tenant isolation
- deployment repeatability

**Опционально перед широким запуском:** rate limiting tuning, notification retry improvements, monitoring dashboards.

---

## Success Criteria of Controlled Launch

Запуск считается успешным, если:

- booking lifecycle работает надёжно
- операторы принимают систему
- reminders снижают no-show
- multi-tenant система стабильна
- onboarding новых СТО становится предсказуемым

---

## Final Outcome

После успешного controlled launch система переходит в **SaaS Expansion Phase**: automated onboarding, tariff plans, SaaS admin tools, рост сети СТО.

---

# Russian Market Launch Adaptation

Auto-Concierge запускается на российском рынке автосервисов (СТО).  
Это влияет на стратегию внедрения и привлечения первых клиентов.

## Главная особенность рынка

**Telegram — основной канал коммуникации с клиентами.**

Поэтому продукт строится вокруг:

- Telegram Bot
- Telegram WebApp
- операторский интерфейс

а не вокруг классического web-сайта.

---

## Особенности российских СТО

Большинство автосервисов в РФ:

- не имеют полноценной CRM
- используют телефон + WhatsApp + Telegram
- ведут запись в тетради или Excel
- оператор отвечает вручную

**Типичный workflow:**

```
клиент пишет → администратор отвечает → предлагает время → записывает вручную
```

Auto-Concierge заменяет именно этот процесс, а не сложные CRM-системы.

---

## Позиционирование продукта

**Для российского рынка продукт должен позиционироваться как:**

> Telegram-бот для записи в автосервис

**а не как:**

> SaaS-платформа для управления сервисным бизнесом

Первые формулировки продают. Вторые — пугают.

---

## Кого брать в пилот

### Идеальные первые клиенты

**1. Частные СТО**

- Размер: 2–6 постов
- Штат: 1 администратор, 2–5 механиков
- Проблема: администратор постоянно отвечает в Telegram  
→ Идеальный кейс для продукта.

**2. Специализированные сервисы**

- шиномонтаж, BMW/VAG сервис, детейлинг, кузовной ремонт
- поток клиентов, повторные записи, Telegram уже используется

### Кого НЕ брать в пилот

- **Крупные сетевые сервисы** — у них уже есть 1С, CRM, call-центр
- **Гаражные сервисы** — 1 мастер, нет администратора, автоматизация не окупается

---

## Как искать первые СТО в России

| Канал | Действия |
|-------|----------|
| **Telegram** | Поиск: «СТО + город», «автосервис + город», каналы и чаты. Прямые сообщения владельцам. |
| **Яндекс Карты** | Карточки «Автосервис», «Шиномонтаж», «Детейлинг» → телефон, Telegram, WhatsApp → предложение. |
| **Авто-сообщества** | Drive2, Telegram чаты автомехаников, локальные авто-группы. |

---

## Как делать предложение

**Нельзя:** «Мы SaaS платформа».

**Нужно:** «Мы сделали Telegram-бота, который автоматически записывает клиентов в автосервис и напоминает о записи. Сейчас тестируем на нескольких СТО. Можно подключить бесплатно на пилот.»

---

## Предложение пилотным СТО

**Формат:** 30 дней бесплатно.

**СТО получает:** Telegram-бот записи, автоматические напоминания, управление записями.

**Мы получаем:** обратную связь, реальные сценарии, разрешение использовать кейс.

---

## Реальная цель первых 10 СТО

**Не деньги.**

**Цель:** product validation.

Проверить:

- как операторы реально работают
- какие функции им нужны
- где ломается UX

---

## Самая важная метрика

**Не регистрации.**

**А:** реальные записи через бота.

Если сервис получает 5–10 записей через бота в неделю — продукт начинает жить.

---

## Что обычно всплывает в России

На пилоте почти всегда появляются:

1. нестандартные услуги
2. нестандартные длительности работ
3. просьбы «добавить комментарий клиента»
4. просьбы «перекинуть запись мастеру»

Это нормальный этап продукта.

---

## Когда можно масштабировать

Когда **5–10 СТО** работают без ручной помощи — можно запускать массовое подключение.

---

## Реальность российского рынка

У СТО очень простая логика.

Если система:

- приводит клиентов  
- экономит время администратора  

они будут платить. Если нет — не будут.

---

## Честный ориентир

**10 СТО**, которые реально используют систему через 1–2 месяца — это очень хороший результат.
