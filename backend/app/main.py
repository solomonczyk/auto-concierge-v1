from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time as time_module
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.rate_limit import limiter
from app.api.api import api_router

from contextlib import asynccontextmanager
from app.bot.loader import dp, bot
from app.bot.handlers import router as bot_router

import logging
import sys
import asyncio

import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logging.getLogger("aiogram").setLevel(logging.INFO)
logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Lifespan startup initiated")
    yield
    # Shutdown
    logger.info("Lifespan shutdown initiated")

# Disable Swagger/OpenAPI in production — reduces attack surface
_docs = None if settings.is_production else "/docs"
_redoc = None if settings.is_production else "/redoc"
_openapi = None if settings.is_production else f"{settings.API_V1_STR}/openapi.json"

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url=_docs,
    redoc_url=_redoc,
    openapi_url=_openapi,
    lifespan=lifespan
)

# Add rate limiter
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please try again later.",
            "retry_after": exc.detail
        }
    )

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Fallback/Dev defaults
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

from app.core.context import tenant_id_context
from jose import jwt, JWTError

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
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            tenant_id = payload.get("tenant_id")
        except Exception:
            pass
            
    # Set context
    token_ctx = tenant_id_context.set(tenant_id)
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"Middleware error: {e}")
        # Re-raise to let FastAPI handle it
        raise
    finally:
        tenant_id_context.reset(token_ctx)

@app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} → {response.status_code}")
    return response

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """
    Deep health check: verifies DB and Redis connectivity.
    Returns 200 only when all critical dependencies are reachable.
    UptimeRobot / any monitor should alert on non-200.
    """
    from sqlalchemy import text
    from app.db.session import async_session_local
    from app.services.redis_service import RedisService

    checks: dict[str, str] = {}
    start = time_module.monotonic()

    # --- PostgreSQL ---
    try:
        async with async_session_local() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        logger.error("[health] DB check failed: %s", exc)
        checks["db"] = f"error: {type(exc).__name__}"

    # --- Redis ---
    try:
        redis = RedisService.get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.error("[health] Redis check failed: %s", exc)
        checks["redis"] = f"error: {type(exc).__name__}"

    elapsed_ms = round((time_module.monotonic() - start) * 1000)
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
