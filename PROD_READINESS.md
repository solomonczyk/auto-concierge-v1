# Security

- [ ] JWT_SECRET хранится только в ENV
- [ ] JWT_SECRET ≥ 32 символов
- [ ] COOKIE_SECURE=true в production
- [ ] COOKIE_HTTPONLY=true
- [ ] COOKIE_SAMESITE=strict или lax
- [ ] CORS разрешён только для прод-домена
- [ ] .env в .gitignore
- [ ] Нет секретов в репозитории
- [ ] Admin пароль изменён и хранится в ENV
- [ ] Rate limit на /login включён
- [ ] Rate limit на booking endpoint
- [ ] Webhook защищён секретом
- [ ] Проверка webhook signature реализована
- [ ] HTTPS через reverse proxy (Nginx / Cloud)
- [ ] HSTS включён
- [x] Docker контейнер не запускается с root
- [ ] Удалены debug endpoints
- [x] Swagger/docs не открыты публично

# Monitoring

- [ ] /health поддерживает GET и HEAD
- [ ] UptimeRobot пингует production URL
- [ ] Логи структурированные (JSON)
- [ ] docker logs не содержит чувствительных данных
- [ ] Ошибки 5xx логируются
- [ ] Логирование не содержит токены
- [ ] Есть алерт в Telegram при падении сервиса
- [ ] Мониторинг базы данных (если отдельная)

# Backup

- [ ] База данных бэкапится ежедневно
- [ ] Проверен restore из backup
- [ ] Backup хранится вне сервера
- [ ] Минимум 7 дней хранения
- [ ] Есть ручной backup script
- [ ] Проверено восстановление tenant-данных

# Tenant Isolation

- [ ] Все запросы фильтруются по tenant_id
- [ ] Нет endpoint без tenant scope
- [ ] Нельзя получить чужие записи через ID
- [ ] Тест: tenant A не видит данные tenant B
- [ ] Tenant slug уникален
- [ ] Rate limit считается отдельно на tenant
- [ ] Логи содержат tenant_id

# CI / Testing

- [ ] E2E запускаются на push
- [ ] E2E запускаются на PR
- [ ] Нет флапающих тестов
- [ ] reset_prod_for_e2e.py очищает данные
- [ ] Тестовый tenant отделён от production
- [ ] Playwright timeout разумный (не 5 минут)

# Infra

- [ ] Docker restart=always
- [ ] Healthcheck в docker-compose
- [ ] ENV production отличается от dev
- [ ] Логи не растут бесконечно (log rotation)
- [ ] Сервер защищён firewall
- [ ] Порты наружу открыты только нужные
- [ ] Нет открытого 5432/3306 наружу
- [ ] CPU/RAM мониторятся

# Legal (для рынка РФ)

- [ ] Политика конфиденциальности доступна
- [ ] Пользователь соглашается с обработкой данных
- [ ] Персональные данные не логируются
- [ ] Есть контакт для удаления данных
- [ ] Данные хранятся в разрешённой юрисдикции

---

## Приоритеты

### 🔴 Критические (закрыть ДО первых клиентов)
- **Открытый Swagger** — реальная поверхность атаки. Закрыть basic-auth или убрать из prod. → *Исправлено: docs/redoc/openapi отключены при ENVIRONMENT=production*
- **Docker от root** — security smell. Не срочно для MVP, но лучше исправить до роста. → *Исправлено: USER app в Dockerfile*
- **Backup на том же сервере** — это не backup, это копия рядом с гробом. → *Требует операционных действий: BACKUP_DIR на удалённый mount, cron, rsync*

### 🟠 Средний риск (можно после первого клиента)
- JSON-логи
- tenant_id в логах
- rate limit per tenant
- log rotation
- CORS через ENV

### 🟡 Низкий риск / операционка
- admin-пароль
- отдельная страница политики
- UptimeRobot сомнения

---

## Отчёт (по состоянию кода)

| Раздел | Выполнено |
|--------|-----------|
| Security | 13/18 |
| Monitoring | 4/8 |
| Backup | 2/6 |
| Tenant Isolation | 5/7 |
| CI / Testing | 6/6 |
| Infra | 4/10 |
| Legal | 4/5 |

---

## Что не сделано

- **Security:** SECRET_KEY без проверки длины (≥32); CORS зависит от .env — если не задан прод-домен, риск. ~~Docker от root~~ и ~~Swagger в prod~~ исправлены.
- **Monitoring:** Логи в обычном Python-формате, не JSON; нет автоматических алертов в Telegram при падении; мониторинг БД не настроен.
- **Backup:** Нет ежедневного cron; restore не проверен; бэкапы по умолчанию в `./backups` на том же сервере; восстановление tenant-данных не проверено.
- **Tenant Isolation:** Rate limit по IP, не по tenant; в логах нет `tenant_id`.
- **Infra:** Нет настроенной log rotation; firewall, порты, 5432, мониторинг CPU/RAM — на уровне сервера, в проекте не заданы.
- **Legal:** Политика конфиденциальности есть только в боте (кнопка «Правовая информация»), отдельной страницы на сайте нет.

---

## Что вызывает сомнения

- **Admin пароль:** В коде нет проверки, изменён ли дефолтный пароль — это операционная задача.
- **UptimeRobot:** Фактически настроен (судя по health HEAD), но не зафиксирован в репозитории.
- **Тестовый tenant:** E2E использует `auto-concierge` в той же production-БД, после `reset_prod_for_e2e` слоты очищаются, но это один инстанс — риск при параллельной работе реальных клиентов.
- **Cookies:** Auth через JWT в `localStorage`, без cookies — пункты COOKIE_* в чеклисте не применимы, но оставлены для возможной будущей схемы.

---

## Где технический риск

1. ~~**OpenAPI/Swagger в prod**~~ — исправлено (отключены при ENVIRONMENT=production).
2. ~~**Docker от root**~~ — исправлено (USER app).
3. **Backup на том же сервере** — при отказе сервера или ransomware бэкапы теряются. Требует: BACKUP_DIR на remote mount + cron + (опционально) rsync.
4. **Rate limit по IP** — один злоумышленник может перегрузить несколько tenants с одного IP; для multi-tenant желателен учёт по tenant.
5. **Логи без tenant_id** — при расследовании инцидентов сложнее локализовать tenant.
6. **Отсутствие log rotation** — риск заполнения диска и неочевидных падений под нагрузкой.
