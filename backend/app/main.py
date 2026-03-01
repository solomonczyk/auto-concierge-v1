from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
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

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Lifespan startup initiated")
    yield
    # Shutdown
    logger.info("Lifespan shutdown initiated")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
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
    # Try to get tenant_id from JWT token
    auth_header = request.headers.get("Authorization")
    tenant_id = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            # We use options={"verify_exp": False} for the middleware if we just want the ID
            # but better to just try/except normally.
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            tenant_id = payload.get("tenant_id")
        except Exception:
            # If token is invalid/expired, we just treat it as unauthenticated
            pass
            
    # FALLBACK FOR WEBAPP/CLIENTS
    if not tenant_id and settings.ENVIRONMENT == "production":
        tenant_id = 3 # Default for the current production bot

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

@app.get("/health")
async def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}

@app.get("/")
async def root():
    return {"message": "Welcome to Autoservice API"}
