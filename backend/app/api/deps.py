from typing import Annotated
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.models.models import User, Tenant
from app.services.tenant_lifecycle_guard import check_tenant_operational_status

AUTH_COOKIE_NAME = "access_token"

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)
optional_bearer = HTTPBearer(auto_error=False)


def _extract_token(request: Request, bearer_token: str | None = None) -> str | None:
    """Cookie-first, then Bearer header fallback (Swagger / API clients)."""
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        return token
    if bearer_token:
        return bearer_token
    return None


async def get_current_user(
    request: Request,
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _extract_token(request, bearer_token)
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_user_optional(
    request: Request,
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_bearer)] = None,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token and auth and auth.credentials:
        token = auth.credentials
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except JWTError:
        return None


async def get_current_tenant_id(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
) -> int:
    from app.core.context import tenant_id_context
    ctx_tenant_id = tenant_id_context.get()
    tenant_id = ctx_tenant_id if ctx_tenant_id is not None else (current_user.tenant_id if current_user else None)

    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated and no tenant context",
        )

    operational, _ = await check_tenant_operational_status(db, tenant_id)
    if not operational:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is suspended or disabled",
        )
    return tenant_id


from app.models.models import UserRole


def require_role(allowed_roles: list[UserRole]):
    def role_checker(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user
    return role_checker


def require_superadmin(current_user: User = Depends(get_current_active_user)) -> User:
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin access required",
        )
    return current_user
