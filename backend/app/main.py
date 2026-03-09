import asyncio
import logging
import os
import sys
import time as time_module
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi.errors import RateLimitExceeded
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.rate_limit import limiter
from app.core.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS_TOTAL, HTTP_ERROR_TOTAL
from app.api.api import api_router
from app.bot.loader import dp
from app.bot.handlers import router as bot_router
from app.workers.outbox_worker import run_outbox_worker

configure_logging()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Sentry: init only if DSN is set
if getattr(settings, "SENTRY_DSN", None):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.asyncio import AsyncioIntegration

    def _before_send(event, hint):
        # Mask sensitive data
        if "request" in event:
            for key in ("cookies", "headers", "data"):
                if key in event.get("request", {}):
                    event["request"][key] = "[Filtered]"
        return event

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=getattr(settings, "RELEASE_VERSION", None) or "auto-concierge@1.0",
        integrations=[FastApiIntegration(), AsyncioIntegration()],
        before_send=_before_send,
        traces_sample_rate=0.1,
    )
logging.getLogger().setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logging.getLogger("aiogram").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Lifespan startup initiated")
    if settings.ENABLE_OUTBOX_WORKER:
        app.state.outbox_worker_task = asyncio.create_task(run_outbox_worker())
        logger.info("Outbox worker started")
    yield
    logger.info("Lifespan shutdown initiated")
    task = getattr(app.state, "outbox_worker_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    try:
        from app.services.redis_service import RedisService
        await RedisService.close()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.warning("Redis shutdown: %s", e)
    try:
        from app.db.session import engine
        await engine.dispose()
        logger.info("DB engine disposed")
    except Exception as e:
        logger.warning("DB shutdown: %s", e)


_docs = None if settings.is_production else "/docs"
_redoc = None if settings.is_production else "/redoc"
_openapi = None if settings.is_production else f"{settings.API_V1_STR}/openapi.json"

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url=_docs,
    redoc_url=_redoc,
    openapi_url=_openapi,
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    rid = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    response = JSONResponse(
        status_code=429,
        content={
            "detail": "Too Many Requests. Please try again later.",
            "error": "rate_limit_exceeded",
            "limit": str(exc.detail),
        },
    )
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log unhandled exceptions (not HTTPException) with stack trace; return sanitized 500."""
    from fastapi import HTTPException as FastAPIHTTPException
    if isinstance(exc, FastAPIHTTPException):
        raise exc
    rid = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    logger.exception(
        "Unhandled exception: %s",
        exc,
        extra={
            "request_id": rid,
            "path": request.url.path,
            "method": request.method,
        },
    )
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
    response.headers["X-Request-ID"] = rid
    return response


if settings.is_production and ("*" in settings.BACKEND_CORS_ORIGINS):
    raise ValueError(
        "Wildcard CORS origin is not allowed with credentials in production!"
    )

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

from app.core.context import tenant_id_context
from app.core.csrf import csrf_middleware
from jose import jwt, JWTError


# ---------------------------------------------------------------------------
# Middleware: request_id (outermost — runs first, so all responses get X-Request-ID)
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# ---------------------------------------------------------------------------
# Middleware: CSRF (double-submit cookie)
# ---------------------------------------------------------------------------
@app.middleware("http")
async def csrf_protection_middleware(request: Request, call_next):
    return await csrf_middleware(request, call_next)


# ---------------------------------------------------------------------------
# Middleware: tenant context
# ---------------------------------------------------------------------------
@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    tenant_id = None
    if token:
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            tenant_id = payload.get("tenant_id")
        except Exception:
            pass

    token_ctx = tenant_id_context.set(tenant_id)
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error("Middleware error: %s", e)
        raise
    finally:
        tenant_id_context.reset(token_ctx)


# ---------------------------------------------------------------------------
# Middleware: structured request logging + duration histogram
# ---------------------------------------------------------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time_module.monotonic()
    response = await call_next(request)
    elapsed = time_module.monotonic() - start

    path = request.url.path
    method = request.method
    status_code = response.status_code

    rid = getattr(request.state, "request_id", "-")
    tenant_id = tenant_id_context.get()

    logger.info(
        "%s %s -> %s (%.3fs)",
        method,
        path,
        status_code,
        elapsed,
        extra={
            "request_id": rid,
            "tenant_id": tenant_id,
            "method": method,
            "path": path,
            "status": status_code,
            "elapsed_s": round(elapsed, 4),
        },
    )

    # Collapse path params to reduce cardinality
    metric_path = path.split("?")[0]
    HTTP_REQUEST_DURATION.labels(
        method=method, path=metric_path, status=str(status_code)
    ).observe(elapsed)
    HTTP_REQUESTS_TOTAL.labels(method=method, path=metric_path, status=str(status_code)).inc()
    if 500 <= status_code < 600:
        HTTP_ERROR_TOTAL.labels(method=method, path=metric_path).inc()

    return response


# ---------------------------------------------------------------------------
# Prometheus /metrics endpoint
# ---------------------------------------------------------------------------
@app.get("/metrics")
async def prometheus_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Health endpoints: /live (liveness), /ready (readiness), /health (general)
# ---------------------------------------------------------------------------

async def _run_readiness_checks() -> tuple[dict[str, str], float]:
    """Check DB and Redis. Returns (checks dict, elapsed_ms)."""
    from sqlalchemy import text
    from app.db.session import async_session_local
    from app.services.redis_service import RedisService

    checks: dict[str, str] = {}
    start = time_module.monotonic()

    try:
        async with async_session_local() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        logger.error("[readiness] DB check failed: %s", exc)
        checks["db"] = f"unavailable: {type(exc).__name__}"

    try:
        redis = RedisService.get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.error("[readiness] Redis check failed: %s", exc)
        checks["redis"] = f"unavailable: {type(exc).__name__}"

    elapsed_ms = round((time_module.monotonic() - start) * 1000)
    return checks, elapsed_ms


@app.api_route("/live", methods=["GET", "HEAD"])
async def live():
    """Liveness: app is running, no dependency checks."""
    return {"status": "ok", "project": settings.PROJECT_NAME}


@app.api_route("/ready", methods=["GET", "HEAD"])
async def ready():
    """Readiness: DB and Redis must be available. 503 if any dependency down."""
    checks, elapsed_ms = await _run_readiness_checks()
    all_ok = all(v == "ok" for v in checks.values())

    payload = {
        "status": "ok" if all_ok else "not_ready",
        "project": settings.PROJECT_NAME,
        "checks": checks,
        "elapsed_ms": elapsed_ms,
    }

    if not all_ok:
        return JSONResponse(status_code=503, content=payload)
    return payload


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """General health: same as /ready, returns 500 if degraded (backward compat)."""
    checks, elapsed_ms = await _run_readiness_checks()
    all_ok = all(v == "ok" for v in checks.values())

    payload = {
        "status": "ok" if all_ok else "degraded",
        "project": settings.PROJECT_NAME,
        "checks": checks,
        "elapsed_ms": elapsed_ms,
    }

    if not all_ok:
        return JSONResponse(status_code=500, content=payload)
    return payload


@app.get("/")
async def root():
    return {"message": "Welcome to Autoservice API"}
