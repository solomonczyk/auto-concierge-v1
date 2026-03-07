# Этап 1: Security Hardening — Deliverable

## Реализовано

### 1. CSRF-защита (double-submit cookie)
- **Double-submit cookie**: CSRF token в cookie + заголовок `X-CSRF-Token`
- **Проверка**: POST / PATCH / PUT / DELETE с auth cookie требуют заголовок
- **GET** не требует CSRF
- **Исключение**: `/login/access-token` (нет сессии до логина)

### 2. Secure cookie settings
- **Auth cookie** (`access_token`): HttpOnly, Secure (в prod), SameSite=Lax
- **CSRF cookie** (`csrf_token`): не HttpOnly (JS читает для header), Secure (в prod), SameSite=Lax
- Dev/prod: `Secure` зависит от `settings.is_production`

### 3. Rate limiting
- **Login**: 10/minute
- **Webhook**: 120/minute
- В тестах limiter отключён (conftest), кроме теста rate limit

### 4. CORS audit
- Только доверенные origins (localhost:5173, 5174, 3000 по умолчанию)
- Без wildcard с credentials: в production `*` в `BACKEND_CORS_ORIGINS` → ValueError при старте
- `allow_credentials=True` для cookie auth

### 5. Security tests
- CSRF: 403 без header, 200 с корректным header, GET /me без CSRF
- Cookie flags: HttpOnly/SameSite для auth, не HttpOnly для CSRF
- Rate limit: 429 после превышения
- CORS: trusted origin, untrusted rejected, production wildcard fail-fast

---

## Пути к файлам

### Backend (изменённые)
| Файл | Описание |
|------|----------|
| `backend/app/core/csrf.py` | CSRF middleware, generate_csrf_token, csrf_cookie_kwargs, skip login path |
| `backend/app/main.py` | CSRF middleware, CORS check (no wildcard in prod), rate limit handler |
| `backend/app/api/endpoints/login.py` | Cookie kwargs (HttpOnly, Secure, SameSite), CSRF cookie на login/me |
| `backend/app/api/endpoints/webhook.py` | Rate limit 120/min |
| `backend/tests/conftest.py` | client_auth fixture (login + X-CSRF-Token), limiter disabled |

### Frontend (изменённые)
| Файл | Описание |
|------|----------|
| `frontend/src/lib/api.ts` | Interceptor: X-CSRF-Token из cookie для POST/PATCH/PUT/DELETE |

### Тесты
| Файл | Описание |
|------|----------|
| `backend/tests/test_csrf_cookie_auth.py` | CSRF: GET без CSRF, 403 без header, 200 с header |
| `backend/tests/test_security.py` | Cookie flags, rate limit 429, CORS |
| `backend/tests/test_sla.py` | client_auth для SLA endpoints |
| `backend/tests/test_ws_ticket_api.py` | client_auth для ws-ticket |
| `backend/tests/test_ws_ticket_ws_connect.py` | client_auth для WS tests |
| `backend/tests/test_external_integration_fail_safe.py` | client_auth |
| `backend/tests/test_appointments.py` | client/client_auth по необходимости |

---

## Список security-тестов

| Тест | Assert |
|------|--------|
| `test_get_me_works_without_csrf` | GET /me с auth cookie без CSRF → 200 |
| `test_mutating_without_csrf_header_rejected` | POST /auth/logout без X-CSRF-Token → 403, "csrf" в detail |
| `test_mutating_with_csrf_header_succeeds_logout` | POST /auth/logout с X-CSRF-Token → 200 |
| `test_mutating_with_csrf_header_succeeds_create_appointment` | POST /appointments/ с CSRF → 200 |
| `test_mutating_with_csrf_header_succeeds_patch_status` | PATCH status с CSRF → 200 |
| `test_cookie_flags_auth_httponly_samesite` | access_token cookie: HttpOnly, SameSite=Lax |
| `test_cookie_flags_csrf_not_httponly` | csrf_token cookie: НЕ HttpOnly |
| `test_rate_limit_login_returns_429` | 11-й login request → 429, "rate limit" в detail |
| `test_cors_allows_trusted_origin` | Origin localhost:5173 → ACAO = localhost:5173 |
| `test_cors_rejects_untrusted_origin` | Origin evil.example.com → ACAO не wildcard, не evil |
| `test_cors_production_wildcard_raises` | ENVIRONMENT=production + BACKEND_CORS_ORIGINS=* → ValueError при импорте main |

---

## Примеры ответов

### /health (если есть)
```json
{"status": "ok", "project": "Autoservice MVP", "checks": {"db": "ok", "redis": "ok"}, "elapsed_ms": 5}
```

### 403 без CSRF
```json
{"detail": "CSRF token missing or invalid"}
```

### 429 rate limit
```json
{"detail": "Rate limit exceeded. Please try again later.", "retry_after": "..."}
```

---

## Запуск security-тестов

```bash
cd backend
python -m pytest tests/test_csrf_cookie_auth.py tests/test_security.py -v
```
