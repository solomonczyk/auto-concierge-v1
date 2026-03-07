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
from app.db.session import get_db
from app.models.models import User, Tenant

router = APIRouter()

AUTH_COOKIE_NAME = "access_token"


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
    db: AsyncSession = Depends(get_db),
    user: User = Depends(deps.get_current_active_user),
) -> dict:
    """Current user info with tenant_slug (for demo button visibility)."""
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
    return result


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

    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = security.create_access_token(
        user.username,
        role=user.role.value,
        tenant_id=user.tenant_id,
        expires_delta=access_token_expires,
    )

    response = JSONResponse(content={"status": "ok"})
    response.set_cookie(
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **_cookie_kwargs(),
    )
    return response


@router.post("/auth/logout")
async def logout():
    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie(**_cookie_kwargs())
    return response
