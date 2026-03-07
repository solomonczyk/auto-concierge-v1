"""
CSRF protection via double-submit cookie pattern.

- Auth cookie (HttpOnly) — not readable by JS.
- CSRF cookie (not HttpOnly) — frontend reads it, sends in X-CSRF-Token header.
- For mutating methods (POST, PATCH, PUT, DELETE) with auth cookie: require header == cookie.
"""
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

CSRF_COOKIE_NAME = "csrf_token"
AUTH_COOKIE_NAME = "access_token"
MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_cookie_kwargs(*, max_age: int, secure: bool) -> dict:
    return {
        "key": CSRF_COOKIE_NAME,
        "httponly": False,  # Frontend must read it for X-CSRF-Token header
        "secure": secure,
        "samesite": "lax",
        "path": "/",
        "max_age": max_age,
    }


def _skip_csrf_path(path: str) -> bool:
    """Login doesn't require CSRF (no session yet; attacker can't force login without credentials)."""
    return "/login/access-token" in path


async def csrf_middleware(request: Request, call_next):
    """Reject mutating requests with auth cookie but missing/invalid CSRF header."""
    if request.method not in MUTATING_METHODS:
        return await call_next(request)
    if _skip_csrf_path(request.url.path):
        return await call_next(request)

    auth_cookie = request.cookies.get(AUTH_COOKIE_NAME)
    if not auth_cookie:
        return await call_next(request)

    csrf_header = request.headers.get("X-CSRF-Token")
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)

    if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF token missing or invalid"},
        )

    return await call_next(request)
