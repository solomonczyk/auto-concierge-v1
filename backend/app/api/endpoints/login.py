import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.rate_limit import limiter
from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.csrf import (
    generate_csrf_token,
    csrf_cookie_kwargs,
    CSRF_COOKIE_NAME,
)
from app.db.session import get_db
from app.models.models import User, Tenant, TenantStatus
from app.services.audit_service import log_audit

router = APIRouter()
logger = logging.getLogger(__name__)

AUTH_COOKIE_NAME = "access_token"
CSRF_MAX_AGE = 60 * 60 * 24  # 24h, same as typical session


def _cookie_kwargs() -> dict:
    return {
        "key": AUTH_COOKIE_NAME,
        "httponly": True,
        "secure": settings.is_production,
        "samesite": "lax",
        "path": "/",
    }


@router.get("/me")
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(deps.get_current_active_user),
):
    """Current user info with tenant_slug. Sets CSRF cookie for bootstrap."""
    result = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role.value if user.role else None,
        "tenant_id": user.tenant_id,
        "tenant_slug": None,
    }
    if user.tenant_id:
        stmt = select(Tenant).where(Tenant.id == user.tenant_id)
        row = await db.execute(stmt)
        tenant = row.scalar_one_or_none()
        if tenant:
            result["tenant_slug"] = tenant.slug

    rid = getattr(request.state, "request_id", "-")
    logger.info(
        "auth.me user_id=%s tenant_id=%s",
        user.id,
        user.tenant_id,
        extra={"request_id": rid, "user_id": user.id, "tenant_id": user.tenant_id},
    )
    response = JSONResponse(content=result)
    csrf_token = generate_csrf_token()
    response.set_cookie(
        value=csrf_token,
        **csrf_cookie_kwargs(max_age=CSRF_MAX_AGE, secure=settings.is_production),
    )
    return response


@router.post("/login/access-token")
@limiter.limit("10/minute")
async def login_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    stmt = select(User).where(User.username == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    rid = getattr(request.state, "request_id", "-")

    if not user or not security.verify_password(form_data.password, user.hashed_password):
        logger.warning(
            "auth.login_failed username=%s",
            form_data.username,
            extra={"request_id": rid, "event_type": "auth_reject"},
        )
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not user.is_active:
        logger.warning(
            "auth.login_inactive user_id=%s",
            user.id,
            extra={"request_id": rid, "user_id": user.id, "event_type": "auth_reject"},
        )
        raise HTTPException(status_code=400, detail="Inactive user")

    if user.tenant_id:
        tenant_row = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
        tenant = tenant_row.scalar_one_or_none()
        if tenant and tenant.status == TenantStatus.SUSPENDED:
            logger.warning(
                "auth.login_suspended_tenant user_id=%s tenant_id=%s",
                user.id,
                user.tenant_id,
                extra={"request_id": rid, "event_type": "auth_reject"},
            )
            raise HTTPException(
                status_code=403,
                detail="Tenant account is suspended",
            )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(
        user.username,
        role=user.role.value,
        tenant_id=user.tenant_id,
        expires_delta=access_token_expires,
    )

    logger.info(
        "auth.login_ok user_id=%s tenant_id=%s",
        user.id,
        user.tenant_id,
        extra={"request_id": rid, "user_id": user.id, "tenant_id": user.tenant_id},
    )

    await log_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="login_success",
        entity_type="auth",
        entity_id=str(user.id),
        payload_after={"username": user.username, "role": user.role.value if user.role else None},
        source="api",
    )
    await db.commit()

    csrf_token = generate_csrf_token()
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response = JSONResponse(content={"status": "ok"})
    response.set_cookie(
        value=token,
        max_age=max_age,
        **_cookie_kwargs(),
    )
    response.set_cookie(
        value=csrf_token,
        **csrf_cookie_kwargs(max_age=max_age, secure=settings.is_production),
    )
    return response


@router.post("/auth/logout")
async def logout(request: Request):
    rid = getattr(request.state, "request_id", "-")
    logger.info("auth.logout", extra={"request_id": rid})
    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie(**_cookie_kwargs())
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
    )
    return response
