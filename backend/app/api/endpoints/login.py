from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.rate_limit import limiter
from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.models import User

router = APIRouter()

@router.post("/login/access-token")
@limiter.limit("10/minute")  # Rate limit login attempts — 10 allows E2E tests, still blocks brute force
async def login_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    Rate limited to 5 attempts per minute to prevent brute force attacks.
    """
    stmt = select(User).where(User.username == form_data.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.username,
            role=user.role.value,
            tenant_id=user.tenant_id,
            expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }
